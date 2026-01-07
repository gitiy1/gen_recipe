{
  description = "Calibre Ebook Generator Environment";

  inputs = {
    # 使用 unstable 分支以获取较新的 Calibre 版本
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        
        # 定义 Python 环境，包含我们需要的三方库
        myPython = pkgs.python3.withPackages (ps: [
          ps.requests
          ps.feedparser
        ]);

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            myPython           # 带依赖的 Python
            pkgs.calibre       # Calibre 电子书工具
            pkgs.xorg.xvfb     # 虚拟显示服务 (用于无头模式运行 Calibre)
            pkgs.glibcLocales  # 解决潜在的编码问题
          ];

          # 设置环境变量，防止 Calibre 中文乱码或编码报错
          shellHook = ''
            export LOCALE_ARCHIVE="${pkgs.glibcLocales}/lib/locale/locale-archive"
            export LANG=C.UTF-8
            echo "Environment ready: Python $(python --version), Calibre $(ebook-convert --version)"
          '';
        };
      }
    );
}
