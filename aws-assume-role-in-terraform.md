# How to effectively use AWS assume role in Terraform

## Objective

This document describes how to best take advantage of the AWS Terraform
provider's ability to assume roles in AWS to effectively manage permissions.
Information on the benefits of splitting up permissions into separate roles
as well as how to create and provision roles is out of scope.

## Roles

For this example, I will use two basic roles. The first is a `read-only` role
that can be freely used by humans and automation. The second is an `admin`
role that will be used by automation when running `terraform apply` but can
also be used by privileged engineers in exceptional scenarios (eg. the
automation broke and needs fixing).

## Initial Authentication

The way in which a user or system gets its initial AWS access keys
(long lasting user access keys, SAML login, instance profile, etc.) is
irrelevant to the processes I am describing as long as that initial identity
has access to assume the `read-only` and/or `admin` roles. Hopefully the access
keys are short lived and the identity only has permission to assume other roles,
but those specifics are out of scope for this document.

## `profile` vs `assume_role`

There are two main ways to assume a role in the `aws` provider block. The
first is via the `profile` argument. This will use your local `~/.aws/config`
file to discover the role it should assume. See the
[AWS configuring profiles guide][configuring profiles] for more information on
what a profile is and how it works.

<details>
    <summary>Example</summary>

#### `~/.aws/config`:

```
[default]
region = us-east-1
output = json

[profile admin]
role_arn = arn:aws:iam::1234567890:role/admin
source_profile = default

[profile read-only]
role_arn = arn:aws:iam::1234567890:role/read-only
source_profile = default
```

#### Provider:
```terraform
provider "aws" {
  profile = var.profile
}

variable "profile" {
  default     = "read-only"
  description = "AWS profile name"
  type        = string
}
```
</details>

You can also directly assume a role in the provider block via an `assume_role`
block argument.

<details>
    <summary>Example</summary>

#### Provider:
```terraform
provider "aws" {
  assume_role {
    role_arn = var.role_arn
  }
}

variable "role_arn" {
  default     = "arn:aws:iam::1234567890:role/read-only"
  description = "ARN of the AWS role to assume"
  type        = string
}
```
</details>

From a practical perspective, it really doesn't matter if you assume roles via
profiles or `assume_role` blocks. Functionally, they are the same. The main
difference is if you are willing to manage the publishing and distribution of
`~/.aws/config` files in exchange for users getting to use friendlier names,
particularly if you have multiple AWS accounts.

## Usage

As you may have noticed in the examples above, instead of putting a string
for the `profile` or `role_arn`, I used a variable that defaults to using the
`read-only` role. Because of the default value, simply using `terraform plan`
will automatically work using the `read-only` role.

However, when you would like to make changes to AWS resources, simply running
`terraform apply` will fail since the `read-only` role does not have permission
to change any resources in AWS. As a result, you need to tell Terraform to use
the `admin` role instead. You can do so via one of the following methods.

The first method is by passing the variable(s) directly on the command line.

<details>
    <summary>Example</summary>

#### `profile` example:
```bash
terraform apply -var "profile=admin"
```

#### `assume_role` example:
```bash
terraform apply -var "role_arn=arn:aws:iam::1234567890:role/admin"
```
</details>

The other method is using a `.tfvar` file. This method is most useful if you
have multiple providers that are applied with separate roles configured with
[provider aliases][provider aliases].

<details>
    <summary>Example</summary>

#### Command line invocation:
```bash
terraform apply -var-file apply.tfvars
```

#### `apply.tfvars` file examples:
```terraform
profile = "admin"
```

```terraform
role_arn = "arn:aws:iam::1234567890:role/admin"
```
</details>

If your organization's deployment policies require that all ordinary deployments
are executed via automation (Jenkins, Terraform Cloud, Github Actions, etc.),
you can enable all of your Terraform users to safely and seamlessly
`terraform plan` via the default `read-only` role so that only the DevOps
engineers that own the Terraform automation need to be aware of the various
privilaged roles or how to execute an apply using those roles.

## Summary

In summary, taking advantage of the Terraform AWS provider's ability to assume
roles in the ways I've described above is an extremely powerful tool that
greatly simplifies proper user management. It only requires a single set of
access keys to enable access to multiple AWS roles and avoids needing to set
environment variables, using multiple sets of keys or key files, or writing any
secrets to the terraform state file.

[configuring profiles]: https://docs.aws.amazon.com/sdk-for-php/v3/developer-guide/guide_credentials_profiles.html
[provider aliases]: https://www.terraform.io/docs/configuration/providers.html#alias-multiple-provider-configurations
