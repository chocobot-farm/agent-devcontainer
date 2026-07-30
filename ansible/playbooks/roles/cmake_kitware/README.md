# CMake Kitware Role

This Ansible role installs the latest CMake version from Kitware's official repository.

## Example Usage

```yaml
- name: Install Kitware CMake
  hosts: all
  become: true
  roles:
    - { role: cmake_kitware, tags: ["cmake"] }
```

## Notes

This role provides a newer CMake version than what is available in the standard Ubuntu repositories.
