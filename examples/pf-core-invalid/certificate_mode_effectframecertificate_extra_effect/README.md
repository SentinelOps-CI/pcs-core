# Invalid EffectFrameCertificate: extra undeclared effect

Action declares `file.write` in addition to `file.read`; the independent
`PFCoreEffectFrame.v0` allows only `file.read`. Membership must fail.
