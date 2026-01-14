{
  description = "Calibre Environment with WebP Support";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        
        # 定义 Python 环境
        myPython = pkgs.python3.withPackages (ps: [
          ps.requests
          ps.feedparser
        ]);

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            myPython
            pkgs.calibre
            pkgs.xorg.xvfb
            pkgs.glibcLocales
            # --- 关键修复：添加图片处理库 ---
            pkgs.libwebp  # 解决 WebP 报错
            pkgs.imagemagick # 辅助图片处理
            pkgs.optipng     # 辅助图片压缩
          ];

          shellHook = ''
            export LOCALE_ARCHIVE="${pkgs.glibcLocales}/lib/locale/locale-archive"
            export LANG=C.UTF-8
            # 尝试修复 Qt WebP 支持
            export QT_PLUGIN_PATH="${pkgs.qt6.qtimageformats}/lib/qt-6/plugins:$QT_PLUGIN_PATH"
          '';
        };
      }
    );
}
