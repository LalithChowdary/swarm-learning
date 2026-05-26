#!/bin/bash
set -e

echo "Exporting gnu-sed path..."
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:$PATH"

export APLS_IP=192.168.64.6
export HOST_IP=10.79.99.58
export SN_IP=10.79.99.58
export SN_API_PORT=30304

echo "Cleaning up previous containers..."
./scripts/bin/stop-swarm || true
docker rm -f sn1 swop1 swci1 || true

echo "Setting up workspace..."
rm -rf workspace
mkdir workspace
cp -r examples/fraud-detection workspace/
cp -r examples/utils/gen-cert workspace/fraud-detection/

echo "Generating certificates..."
./workspace/fraud-detection/gen-cert -e fraud-detection -i 1

echo "Creating host-1-net..."
docker network create host-1-net || true

echo "Applying sed substitutions..."
sed -i "s+<PROJECT-MODEL>+$(pwd)/workspace/fraud-detection/model+g" workspace/fraud-detection/swci/taskdefs/swarm_fd_task.yaml
sed -i "s+<SWARM-NETWORK>+host-1-net+g" workspace/fraud-detection/swop/swop*_profile.yaml
sed -i "s+<CURRENT-PATH>/examples+$(pwd)/workspace+g" workspace/fraud-detection/swop/swop*_profile.yaml
sed -i "s+<LICENSE-SERVER-ADDRESS>+${APLS_IP}+g" workspace/fraud-detection/swop/swop*_profile.yaml
sed -i "s+<PROJECT-CERTS>+$(pwd)/workspace/fraud-detection/cert+g" workspace/fraud-detection/swop/swop*_profile.yaml
sed -i "s+<PROJECT-CACERTS>+$(pwd)/workspace/fraud-detection/cert/ca/capath+g" workspace/fraud-detection/swop/swop*_profile.yaml

echo "Creating volume and copying wheel..."
docker volume rm sl-cli-lib || true
docker volume create sl-cli-lib
docker container create --name helper -v sl-cli-lib:/data hello-world
docker cp lib/swarmlearning-client-py3-none-manylinux_2_24_x86_64.whl helper:/data
docker rm helper

echo "Starting Sentinel Node (SN)..."
./scripts/bin/run-sn -d --rm --name=sn1 --network=host-1-net --host-ip=${HOST_IP} --sentinel --sn-api-port=${SN_API_PORT} \
--key=workspace/fraud-detection/cert/sn-1-key.pem --cert=workspace/fraud-detection/cert/sn-1-cert.pem \
--capath=workspace/fraud-detection/cert/ca/capath --apls-ip=${APLS_IP} \
-e http_proxy= -e https_proxy= -e HTTP_PROXY= -e HTTPS_PROXY=

echo "Starting Swarm Operator (SWOP)..."
./scripts/bin/run-swop -d --rm --name=swop1 --network=host-1-net --usr-dir=workspace/fraud-detection/swop \
--profile-file-name=swop1_profile.yaml --sn-ip=${SN_IP} --sn-api-port=${SN_API_PORT} --key=workspace/fraud-detection/cert/swop-1-key.pem \
--cert=workspace/fraud-detection/cert/swop-1-cert.pem --capath=workspace/fraud-detection/cert/ca/capath \
-e http_proxy= -e https_proxy= --apls-ip=${APLS_IP} \
--swop-uid 0

echo "Starting Swarm Command Interface (SWCI)..."
./scripts/bin/run-swci --rm --name=swci1 --network=host-1-net --usr-dir=workspace/fraud-detection/swci \
--init-script-name=swci-init --key=workspace/fraud-detection/cert/swci-1-key.pem \
--cert=workspace/fraud-detection/cert/swci-1-cert.pem --capath=workspace/fraud-detection/cert/ca/capath --apls-ip=${APLS_IP} < /dev/null 2>&1 | tee workspace/swci_output.log

echo ""
echo "======================================================"
echo "Deployment Complete!"
echo "Check SN logs:         docker logs -f sn1"
echo "Check ML node logs:    docker logs -f <ml-node-container-id>"
echo "======================================================"
