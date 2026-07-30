# Locale Setup Role

This Ansible role configures the system locale to en_US.UTF-8.

## Example Usage

```yaml
- name: Configure UTF-8 locale
  hosts: all
  become: true
  roles:
    - { role: locale_setup, tags: ["locale_setup"] }
```

## Notes

Proper locale configuration is essential for many applications to function correctly. This role ensures the system is using UTF-8 encoding.
