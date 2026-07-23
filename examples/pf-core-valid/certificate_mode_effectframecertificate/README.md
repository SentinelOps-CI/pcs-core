# Valid EffectFrameCertificate fixture

Valid PF-Core trace exercising **`EffectFrameCertificate`** with an independently
declared `PFCoreEffectFrame.v0` (`effect_frame.json`).

v0 policy: one global frame (`frame_scope_policy: global`) bound via
`evidence_selection.effect_frame_id`. Lean obligations prove
`actionEffectsInFrameD concreteAction concreteDeclaredFrame = true` where
`concreteDeclaredFrame` is emitted from the frame artifact, not `action.effects`.
