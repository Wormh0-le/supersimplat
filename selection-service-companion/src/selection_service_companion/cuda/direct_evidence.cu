// SPDX-License-Identifier: MIT
// SuperSimPlat Direct Evidence ABI v2.
//
// This kernel deliberately owns the accepted front-to-back decision chain for
// both RGB and P/N/V. Keep its sigma/alpha/termination expressions aligned
// with the pinned gsplat 3DGS serial forward kernel.

#include <torch/extension.h>
#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAGuard.h>
#include <cuda.h>
#include <cuda_runtime.h>

#include <cstdint>
#include <vector>

namespace {

constexpr float kAlphaThreshold = 1.0f / 255.0f;
constexpr float kMaximumAlpha = 0.99f;
constexpr float kTransmittanceThreshold = 1.0e-4f;

__global__ void direct_evidence_kernel(
    const float* __restrict__ means2d,
    const float* __restrict__ projected_depths,
    const float* __restrict__ conics,
    const float* __restrict__ colors,
    const float* __restrict__ opacities,
    const float* __restrict__ background,
    const int32_t* __restrict__ isect_offsets,
    const int32_t* __restrict__ flatten_ids,
    const int32_t n_isects,
    const int32_t* __restrict__ local_evidence_ids,
    const float* __restrict__ pixel_weights,
    const int32_t width,
    const int32_t height,
    const int32_t tile_width,
    const int32_t tile_height,
    const bool evidence_enabled,
    const int32_t boundary_capacity,
    float* __restrict__ render_colors,
    float* __restrict__ render_alphas,
    float* __restrict__ evidence_masses,
    int32_t* __restrict__ boundary_rows,
    int32_t* __restrict__ boundary_count,
    int32_t* __restrict__ boundary_overflow) {
    // V2A1 carries the immutable projected-row depth into this boundary. V2A2
    // will consume it for moments; this stage must not alter RGB or P/N/V.
    (void)projected_depths;
    const int32_t pixel = static_cast<int32_t>(blockIdx.x * blockDim.x + threadIdx.x);
    const int32_t pixel_count = width * height;
    if (pixel >= pixel_count) {
        return;
    }

    const int32_t x = pixel % width;
    const int32_t y = pixel / width;
    const int32_t tile_x = x >> 4;
    const int32_t tile_y = y >> 4;
    const int32_t tile = tile_y * tile_width + tile_x;
    const int32_t range_start = isect_offsets[tile];
    const int32_t range_end = tile == tile_width * tile_height - 1
        ? n_isects
        : isect_offsets[tile + 1];
    const float center_x = static_cast<float>(x) + 0.5f;
    const float center_y = static_cast<float>(y) + 0.5f;
    const float positive_weight = evidence_enabled ? pixel_weights[pixel * 4 + 0] : 0.0f;
    const float negative_weight = evidence_enabled ? pixel_weights[pixel * 4 + 1] : 0.0f;
    const float visible_weight = evidence_enabled ? pixel_weights[pixel * 4 + 2] : 0.0f;
    const float boundary_weight = evidence_enabled ? pixel_weights[pixel * 4 + 3] : 0.0f;
    const bool evidence_pixel = evidence_enabled && (positive_weight != 0.0f ||
        negative_weight != 0.0f || visible_weight != 0.0f ||
        boundary_weight != 0.0f);

    float transmittance = 1.0f;
    float rgb0 = 0.0f;
    float rgb1 = 0.0f;
    float rgb2 = 0.0f;
    for (int32_t intersection = range_start; intersection < range_end; ++intersection) {
        const int32_t gaussian = flatten_ids[intersection];
        const float dx = means2d[gaussian * 2 + 0] - center_x;
        const float dy = means2d[gaussian * 2 + 1] - center_y;
        const float conic0 = conics[gaussian * 3 + 0];
        const float conic1 = conics[gaussian * 3 + 1];
        const float conic2 = conics[gaussian * 3 + 2];
        const float sigma = 0.5f * (conic0 * dx * dx + conic2 * dy * dy) +
            conic1 * dx * dy;
        const float visibility = __expf(-sigma);
        const float alpha = fminf(kMaximumAlpha, opacities[gaussian] * visibility);
        if (sigma < 0.0f || alpha < kAlphaThreshold) {
            continue;
        }
        const float next_transmittance = transmittance * (1.0f - alpha);
        if (next_transmittance <= kTransmittanceThreshold) {
            break;
        }
        const float accepted_weight = alpha * transmittance;
        rgb0 += colors[gaussian * 3 + 0] * accepted_weight;
        rgb1 += colors[gaussian * 3 + 1] * accepted_weight;
        rgb2 += colors[gaussian * 3 + 2] * accepted_weight;

        if (evidence_pixel) {
            const int32_t local_id = local_evidence_ids[gaussian];
            if (local_id >= 0) {
                if (positive_weight != 0.0f) {
                    atomicAdd(&evidence_masses[local_id * 4 + 0], accepted_weight * positive_weight);
                }
                if (negative_weight != 0.0f) {
                    atomicAdd(&evidence_masses[local_id * 4 + 1], accepted_weight * negative_weight);
                }
                if (visible_weight != 0.0f) {
                    atomicAdd(&evidence_masses[local_id * 4 + 2], accepted_weight * visible_weight);
                }
                if (boundary_weight != 0.0f) {
                    atomicAdd(&evidence_masses[local_id * 4 + 3], accepted_weight * boundary_weight);
                }
            } else if (local_id == -2) {
                const int32_t position = atomicAdd(boundary_count, 1);
                if (position < boundary_capacity) {
                    boundary_rows[position] = gaussian;
                } else {
                    atomicExch(boundary_overflow, 1);
                }
            }
        }
        transmittance = next_transmittance;
    }

    render_colors[pixel * 3 + 0] = rgb0 + transmittance * background[0];
    render_colors[pixel * 3 + 1] = rgb1 + transmittance * background[1];
    render_colors[pixel * 3 + 2] = rgb2 + transmittance * background[2];
    render_alphas[pixel] = 1.0f - transmittance;
}

void require_cuda_float(const torch::Tensor& tensor, const char* name) {
    TORCH_CHECK(tensor.is_cuda(), name, " must be a CUDA tensor");
    TORCH_CHECK(tensor.scalar_type() == torch::kFloat32, name, " must be float32");
    TORCH_CHECK(tensor.is_contiguous(), name, " must be contiguous");
}

void require_cuda_int32(const torch::Tensor& tensor, const char* name) {
    TORCH_CHECK(tensor.is_cuda(), name, " must be a CUDA tensor");
    TORCH_CHECK(tensor.scalar_type() == torch::kInt32, name, " must be int32");
    TORCH_CHECK(tensor.is_contiguous(), name, " must be contiguous");
}

} // namespace

std::vector<torch::Tensor> rasterize_direct_evidence(
    torch::Tensor means2d,
    torch::Tensor projected_depths,
    torch::Tensor conics,
    torch::Tensor colors,
    torch::Tensor opacities,
    torch::Tensor background,
    torch::Tensor isect_offsets,
    torch::Tensor flatten_ids,
    torch::Tensor local_evidence_ids,
    torch::Tensor pixel_weights,
    int64_t width,
    int64_t height,
    int64_t evidence_count,
    bool evidence_enabled,
    int64_t boundary_capacity) {
    require_cuda_float(means2d, "means2d");
    require_cuda_float(projected_depths, "projected_depths");
    require_cuda_float(conics, "conics");
    require_cuda_float(colors, "colors");
    require_cuda_float(opacities, "opacities");
    require_cuda_float(background, "background");
    require_cuda_int32(isect_offsets, "isect_offsets");
    require_cuda_int32(flatten_ids, "flatten_ids");
    require_cuda_int32(local_evidence_ids, "local_evidence_ids");
    require_cuda_float(pixel_weights, "pixel_weights");
    TORCH_CHECK(width > 0 && height > 0, "image dimensions must be positive");
    TORCH_CHECK(width <= INT32_MAX && height <= INT32_MAX &&
        width <= INT32_MAX / height, "image dimensions exceed the Direct Evidence ABI");
    TORCH_CHECK(evidence_count >= 0 && evidence_count <= INT32_MAX,
        "evidence_count exceeds the Direct Evidence ABI");
    TORCH_CHECK(boundary_capacity > 0 && boundary_capacity <= INT32_MAX,
        "boundary_capacity exceeds the Direct Evidence ABI");
    TORCH_CHECK(means2d.dim() == 3 && means2d.size(0) == 1 && means2d.size(2) == 2,
        "means2d must have shape [1,N,2]");
    const int64_t gaussian_count = means2d.size(1);
    TORCH_CHECK(gaussian_count <= INT32_MAX,
        "gaussian count exceeds the Direct Evidence ABI");
    TORCH_CHECK(projected_depths.sizes() == torch::IntArrayRef({1, gaussian_count}),
        "projected_depths must have shape [1,N]");
    TORCH_CHECK(torch::isfinite(projected_depths).all().item<bool>(),
        "projected_depths must contain only finite values");
    TORCH_CHECK(conics.sizes() == torch::IntArrayRef({1, gaussian_count, 3}),
        "conics must have shape [1,N,3]");
    TORCH_CHECK(colors.sizes() == torch::IntArrayRef({1, gaussian_count, 3}),
        "colors must have shape [1,N,3]");
    TORCH_CHECK(opacities.sizes() == torch::IntArrayRef({1, gaussian_count}),
        "opacities must have shape [1,N]");
    TORCH_CHECK(local_evidence_ids.numel() == gaussian_count,
        "local_evidence_ids must map every render row");
    TORCH_CHECK(background.numel() == 3, "background must have three channels");
    TORCH_CHECK(!evidence_enabled ||
        pixel_weights.sizes() == torch::IntArrayRef({height, width, 4}),
        "enabled pixel_weights must have shape [H,W,4]");
    const int64_t tile_width = (width + 15) / 16;
    const int64_t tile_height = (height + 15) / 16;
    TORCH_CHECK(isect_offsets.numel() == tile_width * tile_height,
        "isect_offsets must cover every tile");
    TORCH_CHECK(flatten_ids.numel() <= INT32_MAX, "too many tile intersections");
    const auto device = means2d.device();
    TORCH_CHECK(projected_depths.device() == device &&
        conics.device() == device && colors.device() == device &&
        opacities.device() == device && background.device() == device &&
        isect_offsets.device() == device && flatten_ids.device() == device &&
        local_evidence_ids.device() == device && pixel_weights.device() == device,
        "all Direct Evidence tensors must be on one CUDA device");

    const c10::cuda::CUDAGuard device_guard(device);
    auto float_options = means2d.options();
    auto int_options = flatten_ids.options();
    auto render_colors = torch::empty({height, width, 3}, float_options);
    auto render_alphas = torch::empty({height, width, 1}, float_options);
    auto evidence_masses = torch::zeros({evidence_count, 4}, float_options);
    auto boundary_rows = torch::empty({boundary_capacity}, int_options);
    auto boundary_count = torch::zeros({1}, int_options);
    auto boundary_overflow = torch::zeros({1}, int_options);

    constexpr int threads = 256;
    const int64_t pixel_count = width * height;
    const int blocks = static_cast<int>((pixel_count + threads - 1) / threads);
    direct_evidence_kernel<<<blocks, threads, 0, at::cuda::getCurrentCUDAStream()>>>(
        means2d.data_ptr<float>(),
        projected_depths.data_ptr<float>(),
        conics.data_ptr<float>(),
        colors.data_ptr<float>(),
        opacities.data_ptr<float>(),
        background.data_ptr<float>(),
        isect_offsets.data_ptr<int32_t>(),
        flatten_ids.data_ptr<int32_t>(),
        static_cast<int32_t>(flatten_ids.numel()),
        local_evidence_ids.data_ptr<int32_t>(),
        pixel_weights.data_ptr<float>(),
        static_cast<int32_t>(width),
        static_cast<int32_t>(height),
        static_cast<int32_t>(tile_width),
        static_cast<int32_t>(tile_height),
        evidence_enabled,
        static_cast<int32_t>(boundary_capacity),
        render_colors.data_ptr<float>(),
        render_alphas.data_ptr<float>(),
        evidence_masses.data_ptr<float>(),
        boundary_rows.data_ptr<int32_t>(),
        boundary_count.data_ptr<int32_t>(),
        boundary_overflow.data_ptr<int32_t>());
    C10_CUDA_KERNEL_LAUNCH_CHECK();
    return {
        render_colors,
        render_alphas,
        evidence_masses,
        boundary_rows,
        boundary_count,
        boundary_overflow,
    };
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, module) {
    module.attr("abi_version") = "supersimplat-direct-evidence-abi/v2";
    module.def("rasterize_direct_evidence", &rasterize_direct_evidence,
        "SuperSimPlat same-decision RGB and Direct Evidence rasterization");
}
