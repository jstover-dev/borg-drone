# borg-drone

[![builds.sr.ht status](https://builds.sr.ht/~jmstover/borg-drone/commits/master.svg)](https://builds.sr.ht/~jmstover/borg-drone/commits/master?)

(yet another) borg wrapper. Configure multiple borg repositories and run commands on some or all of them.

Use at your own peril

## Features
- YAML configuration of target repositories
- Easily run borg commands against multiple repositories
- Automatically synchronise a local borg repo with an offsite backup (requires rclone)

## Limitations
- Only local filesystem and remote SSH repositories are supported

## Dependencies

- borg
- rclone (optional)
- Python 3.5+

## Installation

Install via pip
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
# ~/.config/borg-drone/config.yml
#
# borg-drone configuration consists of two main sections: 'repositories' and 'archives'
#
# Repositories are either "local" or "remote" (SSH) targets where the borg repository will be created.
# Many repositories can be defined in this section, but only those referenced by an archive will be used.
#
# Archives are define the folders to be backed up or excluded, and must reference at least one Repository.


repositories:

  # Local repository definitions
  local:

    # Local backup location A
    local-example-a:
      path: /backups/example-a
      encryption: keyfile-blake2
      prune:
        - keep-daily: 7
        - keep-weekly: 3
        - keep-monthly: 6
        - keep-yearly: 2
      compact: false

    # Local backup location B which will be uploaded to an rclone remote
    local-example-b:
      path: /backups/example-b
      encryption: keyfile
      compact: true
      upload_path: 'b2:backups'


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

    # Enable the --one-file-system borg option
    one_file_system: true
  

  # Backup /etc folder to /backup/example-a/local-conf
  local-conf:
    repositories:
      - local-example-a
    paths:
      - /etc

```

List all configured targets
```shell
$ borg-drone targets

this-machine-1:local-example-a
        paths   │ ~/.ssh, ~/.gnupg, ~/Desktop, ~/Documents, ~/Pictures
        exclude │ **/venv, **/node_modules
        repo    │ local-example-a [/backups/example-a]

this-machine-1:remote-example
        paths   │ ~/.ssh, ~/.gnupg, ~/Desktop, ~/Documents, ~/Pictures
        exclude │ **/venv, **/node_modules
        repo    │ remote-example [ssh://backup@backups.example.com:22/.]

local-conf:local-example-a
        paths   │ /etc
        repo    │ local-example-a [/backups/example-a]
```

The syntax for selecting targets is `[ARCHIVE]:[REPO]` _e.g._
```shell
# Run `borg info` on a single target
$ borg-drone info local-conf:local-example-a

# Run `borg info` on all repositories stored in local-example-a
$ borg-drone info :local-example-a

# Run `borg info` on all repositories for "this-machine-1" archive
$ borg-drone info this-machine-1:

# Run `borg info` on all targets
$ borg-drone info :
```

# Commands

Initialise repositories
```shell
$ borg-drone init [ARCHIVE]:[REPO]
```

Export the keys and password files for backup outside of the repository:

```shell
# These will be required in order to restore the backup!
$ borg-drone key-export [ARCHIVE]:[REPO]

# Clean up the exported key files so they do not hang around on your machine
$ borg-drone key-cleanup
```


Create a new backup (_i.e._ call `borg create` on all repositories)
```shell
$ borg-drone create [ARCHIVE]:[REPO]
```


View repository info. (_i.e._ call `borg info` on all repositories)
```shell
$ borg-drone info [ARCHIVE]:[REPO]
```

List repository files. (_i.e._ call `borg list` on all repositories)
```shell
$ borg-drone list [ARCHIVE]:[REPO]
```


Import an existing key and password into a target
```shell
# Import key and password for archive 'this-machine' on repository 'local-example-a'
$ borg-drone key-import this-machine:local-example-a --keyfile /path/to/keyfile --password-file /path/to/password-file
```

## rclone Uploads

Local repositories can optionally be uploaded to an rclone remote `upload_path` option.

This feature required `rclone` to be installed and configured. A remote must be initialised prior to running `borg-drone create`.
See the [rclone documentation](https://rclone.org/docs/) for details.

Repositories will be uploaded to `<upload_path>/<archive_name>`

_e.g._ Using the following configuration:
```yaml
repositories:
  local:
    usb:
      path: /backup/usb
      encryption: keyfile-blake2
      upload_path: 'b2:backups'
archives:
  archive1:
    repositories:
      - usb
    paths:
      - /data
```

Data will first be backed up to a borg repository located at `/backup/usb`,
then the borg repository itself will be uploaded to the remote path `b2:backups/archive1/`
