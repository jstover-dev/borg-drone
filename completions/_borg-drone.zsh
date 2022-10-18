#compdef borg_drone

__borg_drone_get_archives(){
    # shellcheck disable=SC2046
    _values "archive" "all" $(borg-drone targets | sed -n 's/^\[\(.*\)\]/\1/p')
}

__borg_drone_get_targets(){
    # shellcheck disable=SC2046
    _values "archive" $(borg-drone targets | sed -n 's/^\[\(.*\)\]/\1\\:/p')
}

__borg_drone_output_formats(){
    _values "format" "json" "yaml" "text"
}


_borg_drone(){
    local line

    _arguments -C \
        "1: :(create generate-config info init key-cleanup key-export key-import list targets version)" \
        "*::arg:->args"

    case ${line[1]} in
        generate-config)    _borg_drone_generate_config     ;;
        targets)            _borg_drone_targets             ;;
        init)               _borg_drone_init                ;;
        info)               _borg_drone_info                ;;
        list)               _borg_drone_list                ;;
        create)             _borg_drone_create              ;;
        key-export)         _borg_drone_key_export          ;;
        key-cleanup)        _borg_drone_key_cleanup         ;;
        key-import)         _borg_drone_key_import          ;;
    esac
}

_borg_drone_generate_config(){
    _arguments "(-f --force)[Overwrite file if it exists]"
}

_borg_drone_targets(){
    _arguments {-f,--format}'[Output format (default=text)]:target:__borg_drone_output_formats'
}

_borg_drone_init(){
    _arguments "*:archive:__borg_drone_get_archives"
}

_borg_drone_info(){
    _arguments "*:archive:__borg_drone_get_archives"
}

_borg_drone_list(){
    _arguments "*:archive:__borg_drone_get_archives"
}

_borg_drone_create(){
    _arguments "*:archive:__borg_drone_get_archives"
}

_borg_drone_key_export(){
    _arguments "*:archive:__borg_drone_get_archives"
}

_borg_drone_key_cleanup(){
    _arguments "*::archive:__borg_drone_get_archives"
}

_borg_drone_key_import(){
     _arguments \
        "*::target:__borg_drone_get_targets" \
        "--keyfile[Repository encryption key]:file:_files" \
        "--password-file[Repository password file]:file:_files"
}

_borg_drone "$@"
