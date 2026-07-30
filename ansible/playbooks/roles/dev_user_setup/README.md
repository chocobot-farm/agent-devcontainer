# Development User Setup Role

This Ansible role creates and configures a non-root development user account.
It is opt-in via `setup_user` and is skipped by default, because the
devcontainer image runs as root.

The role rewrites the `user_home` and `dev_user` facts once the account exists,
so every role ordered after it writes into the new user's home.

## Role Variables

| Variable                       | Description                       | Default                                         |
| ------------------------------ | --------------------------------- | ----------------------------------------------- |
| `dev_user_setup_username`      | Username for the development user | `devuser`                                       |
| `dev_user_setup_uid`           | User ID for the development user  | `1001`                                          |
| `dev_user_setup_gid`           | Group ID for the development user | `{{ dev_user_setup_uid }}`                      |
| `dev_user_setup_workspace_dir` | Path to the workspace directory   | `/home/{{ dev_user_setup_username }}/workspace` |

## Example Usage

```yaml
- name: Setup development user
  hosts: all
  become: true
  roles:
    - { role: dev_user_setup, tags: ['dev_user_setup'] }
```
