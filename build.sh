#!/bin/bash
set -e

MOD_NAME="mewt0.smartReconnect"
VERSION=""

while getopts "v:" flag; do
  case "${flag}" in
    v) VERSION=${OPTARG} ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "Usage: ./build.sh -v <version>"
  exit 1
fi

rm -rf ./build
mkdir -p ./build
cp -r ./res ./build/

CONFIG_PATH="./build/res/scripts/client/gui/mods/smartReconnect/Config.py"
perl -i -pe "s/\{\{VERSION\}\}/$VERSION/g" "$CONFIG_PATH"

python2 -m compileall ./build/res

META=$(<meta.xml)
META="${META/\{\{VERSION\}\}/$VERSION}"

cd ./build
echo "$META" > ./meta.xml

OUTPUT="${MOD_NAME}_${VERSION}.wotmod"
rm -f "$OUTPUT"

zip -r -0 -X "$OUTPUT" res -i "*.pyc"
zip -r -0 -X "$OUTPUT" meta.xml

cd ..
cp "./build/$OUTPUT" "./$OUTPUT"
rm -rf ./build

echo "Built $OUTPUT"
