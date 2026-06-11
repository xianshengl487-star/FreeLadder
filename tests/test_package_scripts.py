"""tests/test_package_scripts.py - 打包脚本和模板文件测试"""

from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_build_windows_exists():
    """build_windows.py 应存在"""
    assert (ROOT / "tools" / "build_windows.py").exists()


def test_package_windows_exists():
    """package_windows.py 应存在"""
    assert (ROOT / "tools" / "package_windows.py").exists()


def test_app_launcher_exists():
    """app_launcher.py 应存在"""
    assert (ROOT / "freeladder" / "app_launcher.py").exists()


def test_runtime_check_exists():
    """runtime_check.py 应存在"""
    assert (ROOT / "freeladder" / "runtime_check.py").exists()


def test_start_bat_exists():
    """START.bat 模板应存在"""
    assert (ROOT / "tools" / "START.bat").exists()


def test_readme_package_exists():
    """README_PACKAGE.txt 应存在"""
    assert (ROOT / "tools" / "README_PACKAGE.txt").exists()


def test_readme_mihomo_exists():
    """README_MIHOMO.txt 应存在"""
    assert (ROOT / "tools" / "README_MIHOMO.txt").exists()


def test_install_playwright_bat_exists():
    """install_playwright_chromium.bat 应存在"""
    assert (ROOT / "tools" / "install_playwright_chromium.bat").exists()


def test_check_env_bat_exists():
    """check_env.bat 应存在"""
    assert (ROOT / "tools" / "check_env.bat").exists()


def test_open_config_bat_exists():
    """open_config.bat 应存在"""
    assert (ROOT / "tools" / "open_config.bat").exists()


def test_gitignore_excludes_dist():
    """.gitignore 应排除 dist/"""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "dist/" in gitignore


def test_gitignore_excludes_build():
    """.gitignore 应排除 build/"""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "build/" in gitignore


def test_gitignore_excludes_release():
    """.gitignore 应排除 release/"""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "release/" in gitignore


def test_gitignore_excludes_config_yaml():
    """.gitignore 应排除 config.yaml"""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "config.yaml" in gitignore


def test_gitignore_excludes_db():
    """.gitignore 应排除 *.db"""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.db" in gitignore


def test_config_example_exists():
    """config.example.yaml 应存在"""
    assert (ROOT / "config.example.yaml").exists()


def test_start_bat_has_chcp():
    """START.bat 应包含 chcp 65001"""
    content = (ROOT / "tools" / "START.bat").read_text(encoding="utf-8")
    assert "chcp 65001" in content


def test_start_bat_has_mkdir():
    """START.bat 应包含 mkdir 命令"""
    content = (ROOT / "tools" / "START.bat").read_text(encoding="utf-8")
    assert "mkdir" in content


def test_build_windows_is_compilable():
    """build_windows.py 应能通过编译检查"""
    import py_compile
    result = py_compile.compile(
        str(ROOT / "tools" / "build_windows.py"),
        doraise=True,
    )
    assert result is not None


def test_package_windows_is_compilable():
    """package_windows.py 应能通过编译检查"""
    import py_compile
    result = py_compile.compile(
        str(ROOT / "tools" / "package_windows.py"),
        doraise=True,
    )
    assert result is not None


def test_app_launcher_is_compilable():
    """app_launcher.py 应能通过编译检查"""
    import py_compile
    result = py_compile.compile(
        str(ROOT / "freeladder" / "app_launcher.py"),
        doraise=True,
    )
    assert result is not None
