// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 The OCX Authors

//! Tag deletion for GitHub Packages (`ghcr.io`, `containers.<ghes-host>`), which has no OCI tag DELETE.
//!
//! Contract: the owner type comes from `GET /users/{owner}`; the package's versions are listed with
//! pagination; the delete set is the version carrying the tag, plus the platform-manifest versions only
//! it references, plus the referrer fallback-tag versions (`sha256-<digest>`). A version in that set that
//! carries another tag refuses the run with `prune_shared_version`. A 401 or 403 is the existing
//! `DeleteDenied` (exit 80).

use ocx_package::prune::{DeletePlan, DeleteReport, PruneError, TagDeleter};

use super::{ForgeKind, ForgeToken};

/// Deletes tags by deleting the GitHub Packages versions that carry them.
pub struct GithubPackagesDeleter {
    api_base: String,
    registry: String,
    owner: String,
    package: String,
    token: ForgeToken,
}

impl GithubPackagesDeleter {
    /// A deleter for `owner`'s `package` on `registry`, talking to the REST API at `api_base`.
    #[must_use]
    pub fn new(api_base: String, registry: String, owner: String, package: String, token: ForgeToken) -> Self {
        Self {
            api_base,
            registry,
            owner,
            package,
            token,
        }
    }
}

#[async_trait::async_trait]
impl TagDeleter for GithubPackagesDeleter {
    async fn delete(&self, _plan: &DeletePlan, _report: &mut DeleteReport) -> Result<(), PruneError> {
        let _ = (&self.api_base, &self.registry, &self.owner, &self.package, &self.token);
        unimplemented!("contract: see the module documentation")
    }
}

/// The REST API base for a registry host: `ghcr.io` is `https://api.github.com`, `containers.<host>` is
/// a GitHub Enterprise Server at `https://<host>/api/v3`, anything else has none.
#[must_use]
pub fn api_base_for_registry(host: &str) -> Option<String> {
    if host.eq_ignore_ascii_case("ghcr.io") {
        return Some("https://api.github.com".to_owned());
    }
    let enterprise = host
        .get(.."containers.".len())
        .filter(|prefix| prefix.eq_ignore_ascii_case("containers."))?;
    let rest = &host[enterprise.len()..];
    (!rest.is_empty()).then(|| format!("https://{rest}/api/v3"))
}

/// The forge a registry host implies, or `None` when the host says nothing.
#[must_use]
pub fn forge_for_registry(host: &str) -> Option<ForgeKind> {
    api_base_for_registry(host).map(|_| ForgeKind::GitHub)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ghcr_maps_to_the_public_api() {
        assert_eq!(
            api_base_for_registry("ghcr.io").as_deref(),
            Some("https://api.github.com")
        );
        assert_eq!(forge_for_registry("GHCR.io"), Some(ForgeKind::GitHub));
    }

    #[test]
    fn containers_host_maps_to_enterprise_api() {
        assert_eq!(
            api_base_for_registry("containers.git.acme.example").as_deref(),
            Some("https://git.acme.example/api/v3")
        );
    }

    #[test]
    fn other_hosts_map_to_nothing() {
        for host in [
            "localhost:5000",
            "containers.",
            "docker.io",
            "ghcr.io.evil.example",
            "é",
        ] {
            assert_eq!(api_base_for_registry(host), None, "{host}");
            assert_eq!(forge_for_registry(host), None, "{host}");
        }
    }
}
