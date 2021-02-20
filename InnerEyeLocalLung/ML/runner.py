from pathlib import Path
import os
from InnerEye.ML import runner

def main() -> None:
    current = os.path.dirname(os.path.realpath(__file__))
    project_root = Path(os.path.realpath(os.path.join(current, "..", "..")))
    runner.run(project_root=project_root,
        yaml_config_file=project_root / "InnerEyeLocalLung/settings.yml",
        post_cross_validation_hook=None)

#def main() -> None:
#    run(project_root=fixed_paths.repository_root_directory(),
#        yaml_config_file=fixed_paths.SETTINGS_YAML_FILE,
#        post_cross_validation_hook=default_post_cross_validation_hook)


if __name__ == '__main__':
    main()
