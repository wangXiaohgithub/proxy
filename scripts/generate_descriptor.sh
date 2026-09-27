#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Development only: python -m pip install grpcio-tools==1.75.1 protobuf==6.32.1
python -m grpc_tools.protoc -I vendor/xray --include_imports \
  --descriptor_set_out=vendor/xray/router.desc vendor/xray/app/router/config.proto
