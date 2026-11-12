#!/bin/sh
# Rebuild custom_components/hathway/brand/ from docs/brand/hathway-logo.svg.
# Needs ImageMagick 7 (`magick`). Icon = the red "@" glyph; dark logo = white letters.
set -eu
cd "$(dirname "$0")/.."
src=docs/brand/hathway-logo.svg
out=custom_components/hathway/brand
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
{ sed -n '1,/<path/p' "$src" | sed '$d'; grep -o '<path [^>]*fill="#d0342b"[^>]*/>' "$src"; echo '</svg>'; } > "$tmp/at.svg"
sed 's/#18458a/#ffffff/g' "$src" > "$tmp/dark.svg"
magick -background none -density 1200 "$tmp/at.svg" -trim +repage "$tmp/at.png"
for size in 256 512; do
  inner=$((size * 84 / 100))
  name=icon.png; [ "$size" = 512 ] && name=icon@2x.png
  magick "$tmp/at.png" -resize "${inner}x${inner}" -background none -gravity center \
    -extent "${size}x${size}" -strip "PNG32:$out/$name"
done
for variant in light dark; do
  svg=$src; prefix=; [ "$variant" = dark ] && { svg=$tmp/dark.svg; prefix=dark_; }
  magick -background none -density 1600 "$svg" -trim +repage "$tmp/$variant.png"
  magick "$tmp/$variant.png" -resize x128 -strip "PNG32:$out/${prefix}logo.png"
  magick "$tmp/$variant.png" -resize x256 -strip "PNG32:$out/${prefix}logo@2x.png"
done
