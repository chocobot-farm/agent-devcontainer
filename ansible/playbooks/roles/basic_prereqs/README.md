# Basic Prerequisites Role

This Ansible role installs basic prerequisites required for development, including essential packages, the GNOME Keyring stack, an SSH server, and it enables the Ubuntu universe repository.

## Example Usage

```yaml
- name: Install basic prerequisites
  hosts: all
  become: true
  roles:
    - { role: basic_prereqs, tags: ["basic_prereqs"] }
```
