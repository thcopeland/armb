#!/bin/bash

version=$1
dir=armb-$version

if [ -z $version ]; then
  echo "Usage: ./release.sh VERSION"
  exit 1
fi

mkdir $dir
cp -r src/ $dir/src/
cp __init__.py LICENSE README.md $dir/
find $dir -type d -name __pycache__ -prune -exec rm -rf {} \;

zip $dir.zip -r $dir > /dev/null
rm -rf $dir
