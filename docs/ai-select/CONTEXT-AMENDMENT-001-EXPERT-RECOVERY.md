# AI Select Domain Context Amendment 001 — Expert Recovery

Status: **current vocabulary overlay**  
Accepted: 2026-08-23

This file overrides only the conflicting `User-added View` and acquisition-recovery definitions in root `CONTEXT.md`. All other root glossary terms remain current. The old root definition `User-added View (superseded)` is deprecated by this amendment and must not be used for v2 work.

**Automation-default Acquisition**  
The normal post-Anchor workflow in which the system selects and acquires Views automatically under utility and budget policies. Users are not asked to manage cameras during the running loop.

**Expert Recovery**  
A secondary target-local workflow available when no Acquisition Loop is running and the target is active. It lets an operator add a deliberate observation or start another bounded automatic attempt without restarting the target.  
_Avoid_: default planning dashboard, camera control during a running loop

**User-added View**  
A current v2 recovery capability created from an explicit Editor CameraBinding through `Add Observation / Use Current View`. It uses authoritative RGB and the ordinary Stable Mask, Participation, Direct Evidence, reliability, and identity rules. It is not part of the default automatic happy path.  
_Avoid_: removed capability, planner-owned Generated View

**Continue Acquisition**  
An Expert Recovery intent that starts a fresh bounded Acquisition Loop attempt from exact current stable artifacts. It is not same-attempt replay, identical-input retry, or a persistent Generate More control.

**Add Observation / Use Current View**  
An Expert Recovery intent that captures the current Editor Camera as a User-added View. The observation affects Candidate production only after Stable Mask publication, Inclusion, and current Evidence/recomputation.

**Recovery Candidate Staleness**  
The state produced when a new or revised Stable observation changes Candidate inputs. The prior Candidate remains inspectable but cannot be applied until current recomputation publishes a replacement.
