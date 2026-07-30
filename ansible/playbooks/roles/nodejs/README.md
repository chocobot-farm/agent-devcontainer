# Node.js Role

This Ansible role installs Node.js from the official NodeSource repository
and uses Bun for global JavaScript CLI installation.

## Example Usage

```yaml
- name: Install Node.js
  hosts: all
  become: true
  roles:
    - { role: nodejs, tags: ["nodejs"] }
```

## Notes

This role installs Node.js 24.x. The installation is done using the official
NodeSource repository to ensure the latest stable version is installed.
