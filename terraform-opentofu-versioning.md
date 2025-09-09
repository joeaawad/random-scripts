# Terraform/OpenTofu Versioning

Today I’d like to write about the state of versioning in the Terraform and
OpenTofu world, particularly when they are used at scale. While this document
does provide guidance on some specific usage patterns, it is not intended to be
prescriptive. Instead, it is meant to help highlight some of the trade-offs that
should be considered when deciding how you want to use Terraform or OpenTofu
relative to your company’s scale, degree of centralization, requirements, risk
tolerances, and capacity for toil. This document also assumes that you already
have experience with Terraform or OpenTofu.

For a bit of context, the current releases of Terraform and OpenTofu are v1.13.1
and v1.10.6, respectively. For brevity and to avoid writing “Terraform or
OpenTofu” everywhere, I will use “TF” in these locations, and you can substitute
your tool of choice accordingly. If there is a difference between Terraform and
OpenTofu, I will explicitly call that out and use the specific tool name instead
of “TF”. Additionally, because “root modules” and “child modules” terminology
can be confusing, I will use the word “targets” to refer to “root modules”
(where you run your TF CLI commands) and “modules” to refer to “child modules”
(which are called from other directories via a module block’s “source”
argument).

Fundamentally, TF versioning can be broken down into three main components, each
of which has its own considerations. First, TF itself with the TF CLI. Second, provider management and versioning. Third, management of any shared modules that
you might have, particularly if those are accessed via remote source and/or used
by a wide range of targets owned by different teams. I will address each of
these in turn.

## CLI

Versioning of the TF CLI is quite straightforward. You can either install a
specific version directly from the source or use [tenv] to install and manage
multiple versions of both of these tools.

tenv is the significantly improved successor to [tfenv]. Unlike tfenv, I have
not noticed or found any evidence of performance degradation when using tenv
compared to installing TF directly. tenv allows the version of TF to be set
globally or via a configuration file that lives in the current directory, any
parent directory of the current directory, or the user’s home directory. If this
configuration file exists in the current or a parent directory, tenv will
automatically switch the version of TF as you navigate your file system. As a
result, I strongly recommend that all installation of TF on development machines
be managed by tenv. This way, TF version updates can be propagated via modifying
a TF version file in version control.

Considering automation like runner images, one could either install TF directly
or use tenv to do so. This decision should be determined by company policy.

Installing TF directly guarantees a consistent TF version across the company.
This can be extremely valuable if there are shared modules between teams and
repositories since it would avoid compatibility issues with shared modules due
to the TF version that a given root module uses. However, this configuration
also requires that a central entity is responsible for deciding when to upgrade
the TF version and rolling out the required changes across the organization. In
my experience, TF version updates have generally been very low risk operations
with minimal concern from consuming teams since Terraform v1.0 due to increased
stability guarantees. This may someday be an issue in the event of a major
version release.

Alternatively, a company composed of teams with self-contained TF usage may want
to give each team the ability to manage their own TF upgrade schedule under some
acceptable version policy. In this case, tenv would allow this company to use a
single image for all TF automation by supporting many TF versions in one image.

In some cases, it may be useful to switch between a direct TF installation
approach and a tenv approach. Suppose a company previously chose to install TF
directly in automation, and at some point a new major version of TF is released
that causes contention among teams. In order to accommodate all users, it may be
useful for this company to switch to tenv and allow teams to upgrade TF at their
discretion. The company could also switch back to a direct TF installation once
all teams have completed migration to the new major version. As long as there is
no significant variation in TF version across the organization, switching
between these two usage patterns is relatively easy.

In either case, as long as you have a reasonably small number of repos
containing TF configurations (or are ok having an update script push directly to
base branches), it is relatively simple to update thousands of targets at once.
A single TF version file can exist at the root of each repository and be
inherited by every target contained in that repository by tenv. You can use a
[simple script like this][update-repos] to update these version files.

## Providers

Unlike the CLI itself, versioning of TF providers has long been a significant
pain point as your TF usage expands to hundreds or thousands of TF directories.
While there are a number of available permutations that blend these approaches,
there are 3 main approaches that I will present here.

Regardless of your chosen approach, long-lived provider version pins in `.tf`
files should be avoided in most situations. They are useful for resolving
temporary issues, but long-lived pins are a significant maintenance burden and
increase the risk of conflicting requirements or incompatibilities. If they
exist in a target, they cause more toil in updating the `.terraform.lock.hcl`,
which should generally be used instead if you have the desire to control
provider versions in the target. If they exist in a shared module, they can
cause compatibility issues since you cannot have multiple versions of a provider
in a single target since TF `init` will fail due to inability to satisfy all
constraints. For example, suppose you have a target that calls shared module Foo
which has the AWS provider pinned to `~> 4` and shared module Bar which has the
AWS provider pinned to `~> 5`. TF `init` will fail in this target because no
version of the AWS provider satisfies both those constraints.

The main scenario in which a long-lived provider version pin makes sense is if
you have one or two specific providers that are particularly troublesome and
frequently publish bad releases or breaking changes. This does not usually apply
to Official tier providers like AWS, GCP, or Azure, which are quite well
maintained. Rather, some smaller organizations and individual maintainers
struggle to release and version their TF provider reliably. If you choose to pin
a specific version for such a provider, I encourage you to ensure that those
pins for the provider are kept in sync across your company.

For this portion, I will consider automated TF testing out of scope. Even if you
implement significant testing, it is never fully comprehensive and capable of
catching all possible failure modes. Additionally, many of the most destructive
failure modes that could be caused by provider updates only occur in specific
edge cases that are unlikely to be caught via testing. Most issues your
automated testing is likely to catch would likely have already been caught by
the provider maintainers in their testing prior to the provider being released.

### Avoid Provider Versioning

#### Implementation

You could choose to primarily avoid versioning and version pins. This does not
mean that you never pin the version of a provider, but that you only do so
selectively and hopefully temporarily. This should only be done with the
understanding that by implementing a version pin, a team is increasing their
risk of incompatibility while the pin is in place and that removal of the pin
needs to be prioritized.

To implement this approach, you would omit the `.terraform.lock.hcl` file from
version control. In doing so, your automation will download the latest version
of all unpinned providers upon running TF `init`. When implementing this
approach, I also advise adding the `-upgrade` flag to all `init` commands since
there are scenarios where a `.terraform.lock.hcl` file may already exist in the
directory.

#### Advantages

This approach involves the least amount of toil. Mitigating some of the
downsides mentioned below involve some amount of toil, but the amount of toil
scales based on the number of providers rather than the number of TF
directories. On a net basis, this will be substantially less toil if you are
using TF at scale.

If you use shared modules, this approach minimizes the risk of the same module
resulting in different behavior across distinct invocations due to a difference
in provider versions. Managing shared modules is much simpler when one can
safely assume that all usages of a particular module use identical provider
versions.

As long as the risks are properly understood across the company and signed off
on by leadership, this approach can avoid a situation where a centralized team
is responsible for provider version upgrades. This avoids potential conflict
between this centralized team and application teams (or between application
teams with competing interests) related to TF upgrade decisions and schedules.

New features from providers are available immediately, and individual teams need
not wait for a company-wide TF upgrade process to make use of them.

All security updates to providers roll out upon release.

#### Disadvantages

If a provider pushes a bad release or a major release that includes breaking
changes, you will be impacted if you are using an affected resource. Depending
on the particular release, this could result in the destruction of cloud
resources, particularly if your TF is automatically being applied by a scheduled
trigger and humans are not reviewing the plans. It is more likely, however, that
someone will spot an unexpected change in their TF plan and/or your TF run will
fail during the `validate` or `plan` stage prior to modifying any cloud
resources. In this case, you need to either update all affected usages
immediately or insert a temporary pin of the provider version until all affected
usages can be updated. The temporary pin could be inserted in each affected
target or in a shared module if relevant.

The risk of breaking changes in a major version release can be mitigated two
ways. First, most major providers are quite good about publishing notices when
they are approaching a major release that will contain breaking changes. If you
monitor those notices and the breaking change is something that can be
implemented prior to adopting the new version of the provider, you can
proactively update your usages prior to release of the provider. If a breaking
change cannot be adopted prior to the new major version of the provider being
released, you can preemptively add a temporary major version pin for that
provider in any places containing an affected resource. These resources can be
updated and the pin removed once the new major version is released.

Second, you could maintain your own provider registry and restrict TF to only
use that provider registry. This way, when provider maintainers release a new
version, you can inspect the change log and run tests prior to publishing the
new version to your own provider registry. This is toil, but this toil scales
based on the number of providers that you use, which is likely to be orders of
magnitude smaller than your total number of TF directories.

If your release automation includes promotion across environments, it is
possible that a provider release occurs during your promotion flow. For example,
your release automation could execute TF `apply` in testing environments and
during execution a new version of a provider could be released. This could
result in the first usage of the new provider version occurring in a production
`apply`.

### Centralize Provider Versioning

#### Implementation

In this approach, you completely avoid any versioning in your `.tf` files.
Instead, you use the [Terraform][terraform config file] or
[OpenTofu][opentofu config file] config file to prevent TF from accessing remote
registries for any providers and depend upon a local cache on disk pre-populated
with all allowed providers at their desired versions. Additionally, you would
want to omit the `.terraform.lock.hcl` file in version control and ensure that
it is removed before each `init` command.

#### Advantages

Avoids scaling toil at the rate at which you add targets.

Ensures that all targets use the same version of a given provider.

If you use shared modules, this approach minimizes the risk of the same module
resulting in different behavior across distinct invocations due to a difference
in provider versions. Managing shared modules is much simpler when one can
safely assume that all usages of a particular module use identical provider
versions.

#### Disadvantages

There is no flexibility if different teams need to use different versions of a
provider, even if it is just temporarily. While there are potential ways to
mitigate this, they are generally painful and difficult compared to the other
approaches because the implementation of this approach includes actions that
actively prevent targets from installing a different version of a provider.

This lack of flexibility can cause substantial conflict between teams. If Team A
needs a new version of a provider, they must request some centralized team to
roll out the new version across the company and wait for that request to be
fulfilled. When the centralized team goes to fulfill the request, they could
discover that the TF configuration belonging to Team B would break if they made
this upgrade. Depending on the effort involved, Team B might not have the
capacity or ability to address that issue in a time frame that meets Team A’s
needs. Even worse, the centralized team could roll out the change and Team A
could implement the new feature before anyone realizes that the update broke
Team B. Now, you are in a situation where the status quo means someone is broken
and rolling back would also mean someone is broken. Depending on the strength of
your internal culture and leadership, this raises the risk of toxic conflict and
hostility.

Given the effort involved in updating the centralized cache, it is doubtful that
the cache will be updated frequently. Given that many major providers have
weekly or biweekly releases, this might mean that when you finally upgrade the
cache, it contains a large number of changes. Rolling out large batches of
changes involves much higher risk and makes it harder to isolate the source of
issues.

If your release automation includes promotion across environments, it is
possible that a provider release occurs during your promotion flow depending on
the provider cache implementation and its usage by automation. For example, your
release automation could execute TF `apply` in testing environments, and during
execution a new version of the cache could be released. This could result in the
first usage of the new provider version occurring in a production `apply`.

You would likely want to build tooling to allow developers to use the same
provider cache during local development. This would involve synchronizing local
versions of the provider cache on developer machines and VMs.

### Distributed Provider Versioning

#### Implementation

This option best conforms to the published TF best practices. It takes advantage
of the `.terraform.lock.hcl` file by pinning the version of each provider that
is used in a given target until it is explicitly upgraded by running
`init -upgrade`. Unlike the other approaches, you would make sure that the
`.terraform.lock.hcl` is tracked by git.

#### Advantages

This works great when you have a limited number of targets.

Each team has full control over the versions of each provider that is used in
each of their targets.

Depending upon your target structure, this *might* allow you to have confidence
that the same provider version was used in your staging deployment as is being
used in your production deployment. But this would not necessarily be the case
if you have separate targets for separate environments.

#### Disadvantages

This creates a massive amount of toil as your usage scales into the hundreds or
thousands of targets. While you could potentially automate some of this toil,
that automation would itself increase risk. Furthermore, the efforts involved
may be better redirected to implementing the Avoid Versioning approach and
implementing the mitigations listed there instead.

If you use shared modules, there are huge risks whenever you modify a shared
module because you don’t know what versions of the provider are invoking it and
an older version of the provider might not support the change that you are
making.

### Providers Summary

At the end of the day, this decision is a balancing act of your risk tolerances,
compliance requirements, and capacity for toil considering the scale of your
usage. If you use TF at scale and would like some level of consistency and
shared modules across the company, you will likely have a lower amount of net
risk pursuing the Avoid Provider Versioning or Centralize Provider Versioning
approaches. If you have a limited number of targets, are not concerned with
consistency across the company, and do not have shared modules, then Distributed
Provider Versioning is likely best for you.

## Shared Modules

Given that modules are relatively simple if you only have a single repository or
simply don’t use shared modules, I will limit the scope of this section to
multi-repository setups using remote module source with modules that are shared
across the company.

There are three main decisions to make here: where the remote modules are stored
and how they are accessed in a module’s `source` argument, how granular a module
package is, and how module packages or individual modules are versioned.

### Module Storage

For users of OpenTofu, [as of 1.8.0][opentofu variables in source], you can now
use variables in the module `source` argument. This feature has significant
potential to improve your ability to test and promote changes to modules. There
is not currently an equivalent Terraform capability.

OpenTofu 1.10.0 also recently introduced [OCI Registry Support], but I am going
to consider that out of scope for this document since it is OpenTofu specific
and so new. It also looks like they are planning further changes to that
implementation to support [primary installation of providers] so I think it
makes sense to defer evaluation until this OCI effort is closer to completion.

Each of these options can support any granularity of module packages or
versioning strategy with only relatively slight changes in implementation.

#### Local Source

Given the scope I noted above, this refers to having a part of your pipeline
that, outside of TF, loads the module package(s) onto disk in a known location
that your TF configuration references with local paths. This can both increase
TF efficiency and possibly improve the ability to test and promote changes,
particularly if you are not using OpenTofu \>= 1.8.0. However, this approach
does add significant complexity to your pipeline.

One possible generic implementation option could be using Git submodules, but
there are also a number of other potential implementations depending on your
pipeline tool of choice.

##### Versioning

This depends on how you configure your pipeline since the process is entirely
outside of TF.

##### Upload Process

This depends on how you configure your pipeline since the process is entirely
outside of TF.

##### Testing

This depends on how you configure your pipeline since the process is entirely
outside of TF.

#### Module Registry

HashiCorp provides access to a hosted private module registry for HCP Terraform
customers. If you are not an HCP Terraform customer or are using OpenTofu, there
are [several other options][module registry options] that have their own
implementations of the [module registry protocol].

These registries may be convenient, but essentially all of the functionality
they provide can also be obtained using other types of module sources, sometimes
better.

##### Versioning

The most unique factor of Module Registry is that it is the only type of module
source that supports the `version` meta-argument. This is the most transparent
way to specify version constraint ranges. However, because `version` is a
separate argument on a separate line from the module `source` (which may not
even be adjacent), it can be significantly more complex to search for all usages
of a given module version.

##### Upload Process

This varies depending upon the registry host.

##### Testing

Publish a new version and hope that none of your existing usages have version
constraints that would automatically start using it.

#### Git Source

The most common example is GitHub, but the same functionality is supported with
slightly different syntax for any other Git repository host. One advantage of
Git is that for local development, your developers can utilize their existing
Git credentials and configuration. Additionally, because the module name and
version related information are part of a single argument and file line, it is
easy to find all usages of a given module at a given version with a simple
`grep` or other file search mechanism.

##### Versioning

This can be accomplished by using Git tags or branches depending upon your Git
strategy. SemVer version tags can be implemented and maintained with a
[simple script like this][bump-repo-version-tags]. Alternatively, you could use
branches if you are following a release channel approach. Those tags, branches,
or even commits can then be referenced by adding `?ref=<REF>` to the end of the
source URL.

##### Upload Process

Perform a `git push` and it is instantly available with no extra build or upload
processes required.

##### Testing

Use `?ref=<REF>` at the end of the source URL to test a specified tag, branch or
even commit.

#### File Archive

There are several variations of this that I am going to combine here. They
include generic HTTP URLs, S3 buckets, or GCS buckets that contain a zip or tar
type of archive.

While these options exist, I would strongly recommend choosing one of the above
mentioned options instead. These options involve extensive initial configuration
and introduce a significant lag in automation when creating and uploading new
artifacts.

##### Versioning

This depends on how you configure your pipeline since the process is entirely
outside of TF.

##### Upload Process

This depends on how you configure your pipeline since the process is entirely
outside of TF.

##### Testing

This depends on how you configure your pipeline since the process is entirely
outside of TF.

#### Modules Storage Summary

Local Source, Module Registry, and Git Source can all be great choices depending
on your specific requirements and environment. That said, I think Git Source
provides the best performance and flexibility at the least effort for most
users.

### Module Package Granularity

Regardless of which module storage type you choose, another key decision is if
you would like to publish a single module package that contains all of your
shared modules or separate module packages for each module. There is a middle
ground where you can clump batches of related modules into shared module
packages, but given that this approach has the same types of trade offs as
either end of the spectrum, I will not discuss this here.

#### Single Module Package

##### Implementation

In this approach, you have a single module package that is used as the source
for all shared module usages. You then use [sub-directories] to access
individual modules within that single module package. Any usage of one shared
module by another shared module is done via local paths within the single module
package.

##### Advantages

If your shared modules frequently use or interact with other shared modules,
this reduces the risk of incompatibility issues between separate shared modules
because they are all versioned and released as a single artifact.

##### Disadvantages

This results in increased disk usage and increased `init` times if you use
remote source to access the module package. These impacts are mostly limited to
your local disk and have minimal impact on your network traffic since TF will
only download the module package once from the remote source and then create
multiple copies on disk for each usage. See
[this OpenTofu issue][opentofu module copies] (or
[this Terraform issue][terraform module copies]) for more details. Hopefully
most of the negative impacts will be solved soon. At time of publishing, the
OpenTofu issue appears to have significantly more traction than the Terraform
issue with their respective maintainers.

#### Separate Module Packages

##### Implementation

In this approach, you would have a separate module package for each individual
module.

##### Advantages

This can result in lower network traffic, disk usage, and faster `init` times
because you are only downloading and copying the modules that are actually used.

##### Disadvantages

If you have multiple shared modules that interact with or reference each other,
there is a greatly increased risk of incompatibility between different module
packages because they are versioned and released separately.

### Module Versioning

If each individual module does not have a separate module package, this creates
an additional level of complexity regarding how you version individual modules
within a single module package. You can version the module package as a whole,
have release channels for the module package, version individual modules within
the module package, or some combination of those three.

#### Module Package SemVer Versioning

##### Implementation

When a module package is released, regardless of the granularity of the module
package, you would cut a new SemVer version.

##### Advantages

This allows you to make sure that modules with changes of your desired version
increment level are tested in lower environments and go through a promotion
flow.

##### Disadvantages

This can create significant toil. Particularly if you have larger module
packages containing many distinct modules, it is very noisy to cut a new release
whenever an individual module is updated. Even if most usages are only pinned to
major version increments, you could easily end up with a ton of major version
releases since a breaking change to any individual module would require a major
version bump of the entire module package, which could contain hundreds of
individual modules.

If you attempt to avoid the noise of frequent major version releases by batching
breaking changes, this would create a substantial drag on development velocity
since some changes would need to wait months or even years for the next
scheduled major version release. We frequently see this tension with major
providers like the AWS provider.

#### Module Package Release Channels

##### Implementation

When module updates are made, they would be published to a development release
channel that is used in your lower environments. Once that has been deployed and
is successfully running for a sufficient time period, you would then promote the
module package to your higher environment release channel(s).

##### Advantages

This allows you to test modules in lower environments and go through a promotion
flow.

This has less toil than SemVer versioning of module packages since the callers
do not have to be updated to adopt updates of the module package.

##### Disadvantages

If your TF pipelines are not applied on a regular basis, this can result in
changes being promoted to the production release channel prior to running in
your development environments.

It requires a centralized team that decides when a module package can safely be
promoted to a higher release channel. This can create internal conflict and
tension between teams, particularly on more urgent upgrades.

#### Individual Module Versioning

##### Implementation

Instead of versioning the module package, you could version individual modules
within it and only increment when implementing breaking changes (or other
changes that are flagged as particularly high risk) to a given module. This
would be accomplished by forking the existing module and creating a new
directory with `-v2` or similar appended to the end of the module name prior to
making your changes. To adopt the new version, all callers would have to update
the `source` they are invoking.

This would mean that any change that is not flagged as high risk or breaking
would be rolled out immediately to all callers.

##### Advantages

This would minimize the toil required to adopt most module changes.

Most module updates would be adopted faster and in very limited change sets that
can provide timely feedback if there are any issues.

##### Disadvantages

It requires careful code review and engineering expertise to make sure that high
risk or breaking changes are identified prior to merge and go through the
additional process of forking the existing module.

More thought and care is required to determine how you handle the lifecycle of
old versions of modules. Does the old version continue to be maintained after
the fork? How are callers notified that there is a new version of the module
available? Are old versions removed after a certain time period?

## Summary

One final point that I want to make here is that multiple approaches for a given
component can sometimes be combined if your company has a number of different
teams with different risk profiles and compliance requirements. However, you
must ensure that if there is variation from the company-wide pattern, that the
variation considers each of these components and the holistic impact of changing
strategy for a given component. This may mean that the variation needs to
encompass changes to the approach for multiple components.

For example, the company as a whole could take the Avoid Provider Versioning and
Individual Module Versioning approaches to minimize toil, but a specific team or
two that has more specific compliance needs could have their own branch(es) in
or fork of the shared module repo that allows them to follow the Module Package
Release approach and use Distributed Provider Versioning. Alternatively, you
could Avoid Provider Versioning for most of your providers, but have a limited
subset of your shared modules that use a particularly high-risk provider. In
this case,  you might restrict all usages of that provider to occur through your
shared modules and implement version pins in your shared modules for just that
one provider.

At the end of the day, the general company-wide pattern does not necessarily
have to be engineered to meet the strictest compliance requirements if those
requirements only apply to a small portion of the company and you are ok with
having that variation in usages within the company.

In summary, there are a number of different approaches to versioning the various
components of your TF implementation. It is important to consider each of those
components and how they fit together when determining your TF strategy. There is
no right answer for everyone, but hopefully this document has helped you
understand the risk and toil trade offs involved with the various approaches.

Regardless of which approaches you choose, it is extremely important to gain
alignment across your company, including with compliance and senior leadership,
on these trade offs and documented risk acceptance, particularly if you are
considering embarking on a refactoring of your TF usage patterns. None of the
approaches are risk-free, and at some point there will be an incident. When that
incident happens, it is important to have this documentation and to avoid
over-reacting in a way that may reduce the risk of the specific incident
re-occurring but actually increases your net level of risk.


[bump-repo-version-tags]: https://github.com/joeaawad/random-scripts/blob/master/bump-repo-version-tags.py
[module registry options]: https://github.com/virtualroot/awesome-opentofu?tab=readme-ov-file#registry
[module registry protocol]: https://developer.hashicorp.com/terraform/registry/api-docs
[OCI Registry Support]: https://opentofu.org/docs/intro/whats-new/#oci-registry-support
[opentofu config file]: https://opentofu.org/docs/cli/config/config-file/
[opentofu module copies]: https://github.com/opentofu/opentofu/issues/1086
[opentofu variables in source]: https://github.com/opentofu/opentofu/pull/1718
[primary installation of providers]: https://opentofu.org/docs/main/cli/oci_registries/#opentofu-providers-in-oci-registries
[sub-directories]: https://opentofu.org/docs/language/modules/sources/#modules-in-package-sub-directories
[tenv]: https://github.com/tofuutils/tenv
[terraform config file]: https://developer.hashicorp.com/terraform/cli/config/config-file
[terraform module copies]: https://github.com/hashicorp/terraform/issues/29503
[tfenv]: https://github.com/tfutils/tfenv
[update-repos]: https://github.com/joeaawad/random-scripts/blob/master/update-repos.py
