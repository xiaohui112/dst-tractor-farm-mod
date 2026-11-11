-- 已安装 FMOD Designer 正式编译的《兰花草》音频包。
-- 构建源文件和校验记录见 assets/audio/fmod；缺失任一文件时仍保持静音。
return {
    available=true,
    event="aom_irrigator_music/irrigator/lanhuacao",
    assets={
        {"SOUNDPACKAGE","sound/aom_irrigator_music.fev"},
        {"SOUND","sound/aom_irrigator_music.fsb"},
    },
}
