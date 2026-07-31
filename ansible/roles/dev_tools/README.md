# Development Tools Role

This Ansible role installs a general set of development tools: build tooling
(build-essential, CMake, Ninja, pkg-config), version control (git, git-lfs),
Python packaging basics, `pre-commit`, `shellcheck`, `jq`, `ffmpeg`, `btop`,
and the pinned `zizmor` GitHub Actions auditor.

## Example Usage

```yaml
- name: Install development tools
  hosts: all
  become: true
  roles:
    - { role: dev_tools, tags: ['dev_tools'] }
```
