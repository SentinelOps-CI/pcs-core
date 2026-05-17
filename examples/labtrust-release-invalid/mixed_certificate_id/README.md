# Invalid release chain: mixed certificate ID

This directory intentionally reproduces a **mixed-run** failure: the certified bundle references one `TraceCertificate.certificate_id` while the verification result and signed bundle reference another.

`pcs validate-release-chain` must reject this directory with `mixed_certificate_id`.
