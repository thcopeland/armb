#!/bin/bash

version=$1
dir=armb-$version

if [ -z $version ]; then
  echo "Usage: ./release.sh VERSION"
  exit 1
fi

mkdir $dir
mkdir $dir/armb
cp -r src/ $dir/armb/src/
cp __init__.py LICENSE README.md $dir/armb/
find $dir -type d -name __pycache__ -prune -exec rm -rf {} \;

cd $dir
zip ../$dir.zip -r armb/ > /dev/null
cd ../

rm -rf $dir
