# Bash Setup Role

This Ansible role configures the Bash shell for development: it puts
`~/.local/bin` on `PATH` and enables a large, de-duplicated shell history.

## Example Usage

```yaml
- name: Setup Bash shell
  hosts: all
  roles:
    - { role: bash_setup, tags: ['bash_setup'] }
```
