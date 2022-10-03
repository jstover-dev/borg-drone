# borg-drone

(yet another) borg wrapper.

This application is a helper to run multiple borg backups with a single command.

## Dependencies

- borg
- Python 3.5+

## Installation

Install via pip (WIP)
```shell
pip install borg-drone
```

Install from source (requires pip v21.2 or later)
```shell
git clone https://git.sr.ht/~jmstover/borg-drone
cd borg-drone
pip install .
```

## Usage

Generate a new configuration file
```shell
borg-drone generate-config
```

Edit the configuration file to suit the local backup needs
```yaml
# borg-drone configuration consists of two main sections: 'repositories' and 'archives'
#
# Repositories are local or remote (SSH) targets where the borg repository will be created.
# Many repositories can be defined in this section, but only those referenced by an archive will be used.
#
# Archives are local to the machine running borg-drone and define the folders to be backed up and excluded.
# All archives defined here will be used by default.


repositories:

  # Local repository definitions
  local:

    # Local backup location A
    local-example:
      path: /backups/example-a
      encryption: keyfile-blake2
      prune:
        - keep-daily: 7
        - keep-weekly: 3
        - keep-monthly: 6
        - keep-yearly: 2
      compact: false

    # Local backup location B
    local-example-2:
      path: /backups/example-b
      encryption: keyfile
      compact: true


  # Remote repository definitions
  remote:

    # Remote borg repository located at backups.example.com
    remote-example:
      hostname: backups.example.com
      username: backup
      port: 22
      ssh_key: ~/.ssh/borg
      encryption: repokey-blake2
      prune:
        - keep-daily: 7
        - keep-weekly: 3
        - keep-monthly: 6
        - keep-yearly: 2
      compact: false



archives:

  # Backup definition for this machine
  this-machine:

    # Use multiple repositories as defined above
    repositories:
      - local-example-a
      - remote-example

    # Include the following directories
    paths:
      - ~/.ssh
      - ~/.gnupg
      - ~/Desktop
      - ~/Documents
      - ~/Pictures

    # Exclude the following patterns (these are passed directly to borg)
    exclude:
      - "**/venv"
      - "**/node_modules"

    # Enable the --one-file-system borg options
    one_file_system: true
```

List all configured targets
```shell
borg-drone targets
```


Initialise repositories (This calls `borg init` on all repositories)
```shell
borg-drone init
```

Export the keys and password files for backup outside of the repository.
**These will be required in order to restore the backup!**
```shell
borg-drone key-export
```


Clean up the exported key files so they do not hang around on your machine
```shell
borg-drone key-cleanup
```


Create a new backup (This calls `borg create` on all repositories)
```shell
borg-drone create
```


View repository info. (This calls `borg info` on all repositories)
```shell
borg-drone info
```

List repository files. (This calls `borg list` on all repositories)
```shell
borg-drone list
```


Import an existing key and password into a target
```shell
# Import key and password for archive 'this-machine' on repository 'local-example-a'
borg-drone key-import this-machine:local-example-a --keyfile /path/to/keyfile --password-file /path/to/password-file
```