# Invalid FramePreservedCertificate cross-tenant no-op

Sequential allow events on different tenants. Under `applyEvent`, the second allow
would silently leave state unchanged (`stepState` returns `none`). Remediated
`FramePreservedCertificate` rejects this path and requires `stepState = some post`.
