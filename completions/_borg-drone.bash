#!/usr/bin/env bash

_borg_drone_completions()
{
    local commands=(create generate-config info init key-cleanup key-export key-import list targets version)

    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [ "${COMP_CWORD}" -eq 1 ]; then
        COMPREPLY=($(compgen -W "${commands[*]}" -- "${cur}"))
        return
    fi

    # Determine which subcommand was specified
    cmd=
    for arg in "${COMP_WORDS[@]}"; do
        for command in "${commands[@]}"; do
            if [ "$arg" = "$command" ]; then
                cmd="$command"
                break 2
            fi
        done
    done
    if [ -z "$cmd" ]; then return; fi


    local prev="${COMP_WORDS[COMP_CWORD - 1]}"
    # shellcheck disable=SC2207
    case ${cmd} in
        generate-config)    COMPREPLY=($(compgen -W ""))     ;;
        info)               COMPREPLY=($(compgen -W ""))     ;;
        list)               COMPREPLY=($(compgen -W ""))     ;;
        create)             COMPREPLY=($(compgen -W ""))     ;;
        key-export)         COMPREPLY=($(compgen -W ""))     ;;
        key-cleanup)        COMPREPLY=($(compgen -W ""))     ;;
        key-import)
            case ${prev} in
                --keyfile)          COMPREPLY=($(compgen -f -- "${cur}"))                                   ;;
                --password-file)    COMPREPLY=($(compgen -f -- "${cur}"))                                  ;;
                *)                  COMPREPLY=($(compgen -f -W "--keyfile --password-file" -- "${cur}"))     ;;
            esac
    esac
}

complete -F _borg_drone_completions borg-drone