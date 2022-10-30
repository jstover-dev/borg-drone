import pytest

from borg_drone.config import validate_config, ConfigValidationError


def test_validate_config_keys():
    with pytest.raises(ConfigValidationError) as ex:
        validate_config({})

    assert "Missing required keys: ['archives', 'repositories']" in ex.value.errors
    assert "No repositories were defined" in ex.value.errors

    with pytest.raises(ConfigValidationError) as ex:
        validate_config({'archives': {}})
    assert "Missing required keys: ['repositories']" in ex.value.errors
    assert "No repositories were defined" in ex.value.errors

    with pytest.raises(ConfigValidationError) as ex:
        validate_config({'repositories': {}})
    assert "Missing required keys: ['archives']" in ex.value.errors
    assert "No repositories were defined" in ex.value.errors


def test_validate_config_repo_references():
    # Validate repository references
    with pytest.raises(ConfigValidationError) as ex:
        validate_config(
            {
                'repositories': {
                    'local': {
                        'repo1': {},
                        'repo2': {}
                    }
                },
                'archives': {
                    'archive1': {
                        'repositories': [
                            'repo1',
                            'repo2',
                        ]
                    }
                }
            })
    assert not any('Invalid repository reference' in x for x in ex.value.errors)

    with pytest.raises(ConfigValidationError) as ex:
        validate_config(
            {
                'repositories': {
                    'local': {
                        'repo1': {},
                    }
                },
                'archives': {
                    'archive1': {
                        'repositories': [
                            'unreferenced',
                        ]
                    }
                }
            })
    assert 'Invalid repository reference: unreferenced' in ex.value.errors


def test_validate_config_duplicate_repository_names():
    with pytest.raises(ConfigValidationError) as ex:
        validate_config(
            {
                'repositories': {
                    'local': {
                        'dupe_repo': {},
                    },
                    'remote': {
                        'dupe_repo': {},
                    }
                },
                'archives': {}
            })
    assert 'Duplicate repository name: dupe_repo' in ex.value.errors


def test_validate_config_prune_options():
    with pytest.raises(ConfigValidationError) as ex:
        validate_config({
            'repositories': {
                'local': {
                    'repo1': {
                        'prune': [
                            {
                                'bad_option': 1
                            },
                        ]
                    },
                }
            },
            'archives': {},
        })
    assert "Invalid prune options: [{'bad_option': 1}]" in ex.value.errors

    # Validate all prune options
    with pytest.raises(ConfigValidationError) as ex:
        validate_config(
            {
                'repositories': {
                    'local': {
                        'repo1': {
                            'prune': [
                                {
                                    'keep_hourly': 1
                                },
                                {
                                    'keep_daily': 2
                                },
                                {
                                    'keep_weekly': 3
                                },
                                {
                                    'keep_monthly': 4
                                },
                                {
                                    'keep_yearly': 5
                                },
                            ]
                        },
                    }
                },
                'archives': {},
            })
    assert not any("Invalid prune options" in x for x in ex.value.errors)

    # Validate partial prune options
    with pytest.raises(ConfigValidationError) as ex:
        validate_config({
            'repositories': {
                'local': {
                    'repo1': {
                        'prune': [
                            {
                                'keep_hourly': 1
                            },
                        ]
                    },
                }
            },
            'archives': {},
        })
    assert not any("Invalid prune options" in x for x in ex.value.errors)


def test_validate_config_invalid_repo_type():
    with pytest.raises(ConfigValidationError) as ex:
        validate_config({
            'repositories': {
                'invalid_name': {},
                'local': {
                    'repo1': {}
                },
            },
            'archives': {},
        })
    assert "Invalid repository types: {'invalid_name'}" in ex.value.errors


def test_validate_config_multiple_errors():
    with pytest.raises(ConfigValidationError) as ex:
        validate_config(
            {
                'repositories': {
                    'local': {
                        'repo1': {
                            'prune': [
                                {
                                    'bad_option': 1
                                },
                            ]
                        },
                    },
                    'remote': {
                        'repo1': {},
                    },
                    'bananas': {},
                },
                'archives': {
                    'archive1': {
                        'repositories': [
                            'repo1',
                            'unreferenced',
                        ]
                    }
                },
            })
    assert ex.value.errors == {
        "Duplicate repository name: repo1",
        "Invalid repository types: {'bananas'}",
        "Invalid prune options: [{'bad_option': 1}]",
        "Invalid repository reference: unreferenced",
        'Archive "archive1" is missing attribute "paths"',
        'Repository "repo1" is missing attribute "hostname"',
        'Repository "repo1" is missing attribute "encryption"',
        'Repository "repo1" is missing attribute "path"',
    }


@pytest.mark.parametrize(
    'upload_path, is_valid', [
        (None, True),
        ('', True),
        ('remote', False),
        ('remote:', True),
        ('remote:a', True),
        ('remote:/a', True),
        ('remote:a/b', True),
    ])
def test_validate_config_rclone_upload_path(config_data: dict, upload_path: str, is_valid: bool):
    test_config = config_data.copy()
    first_repo = list(test_config['repositories']['local'].keys())[0]
    test_config['repositories']['local'][first_repo]['rclone_upload_path'] = upload_path

    if is_valid:
        validate_config(test_config)

    else:
        with pytest.raises(ConfigValidationError) as ex:
            validate_config(test_config)
        assert ex.value.errors == {
            f'Invalid rclone_upload_path "{upload_path}". Path must contain a single colon',
        }
