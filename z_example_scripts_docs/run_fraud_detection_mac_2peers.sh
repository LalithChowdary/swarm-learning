#!/bin/bash
set -e

echo "Exporting gnu-sed path..."
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:$PATH"

export APLS_IP=192.168.64.6
export HOST_IP=10.79.51.89
export SN_IP=10.79.51.89
export SN_API_PORT=30304

echo "Cleaning up previous containers..."
./scripts/bin/stop-swarm || true
docker rm -f sn1 swop1 swci1 || true

echo "Setting up workspace..."
rm -rf workspace/fraud_Detection_2pears
mkdir -p workspace/fraud_Detection_2pears
cp -r examples/fraud-detection/* workspace/fraud_Detection_2pears/
cp -r examples/utils/gen-cert workspace/fraud_Detection_2pears/

echo "Merging node 4 data into node 1..."
tail -n +2 workspace/fraud_Detection_2pears/data-and-scratch4/app-data/SB19_CCFDUBL_TRAIN.csv >> workspace/fraud_Detection_2pears/data-and-scratch1/app-data/SB19_CCFDUBL_TRAIN.csv
tail -n +2 workspace/fraud_Detection_2pears/data-and-scratch4/app-data/SB19_CCFDUBL_TEST.csv >> workspace/fraud_Detection_2pears/data-and-scratch1/app-data/SB19_CCFDUBL_TEST.csv
rm -rf workspace/fraud_Detection_2pears/data-and-scratch4/

echo "Merging node 3 data into node 2..."
tail -n +2 workspace/fraud_Detection_2pears/data-and-scratch3/app-data/SB19_CCFDUBL_TRAIN.csv >> workspace/fraud_Detection_2pears/data-and-scratch2/app-data/SB19_CCFDUBL_TRAIN.csv
tail -n +2 workspace/fraud_Detection_2pears/data-and-scratch3/app-data/SB19_CCFDUBL_TEST.csv >> workspace/fraud_Detection_2pears/data-and-scratch2/app-data/SB19_CCFDUBL_TEST.csv
rm -rf workspace/fraud_Detection_2pears/data-and-scratch3/

echo "Applying 2 peers configuration changes..."
sed -i "s/MIN_PEERS\": 4/MIN_PEERS\": 2/g" workspace/fraud_Detection_2pears/swci/taskdefs/swarm_fd_task.yaml
sed -i "s/WITH 4 PEERS/WITH 2 PEERS/g" workspace/fraud_Detection_2pears/swci/swci-init
sed -i '/idx : 3/,+31d' workspace/fraud_Detection_2pears/swop/swop1_profile.yaml
sed -i '/idx : 2/,+31d' workspace/fraud_Detection_2pears/swop/swop1_profile.yaml

echo "Generating certificates..."
./workspace/fraud_Detection_2pears/gen-cert -e fraud_Detection_2pears -i 1

echo "Creating host-1-net..."
docker network create host-1-net || true

echo "Applying sed substitutions..."
sed -i "s+<PROJECT-MODEL>+$(pwd)/workspace/fraud_Detection_2pears/model+g" workspace/fraud_Detection_2pears/swci/taskdefs/swarm_fd_task.yaml
sed -i "s+<SWARM-NETWORK>+host-1-net+g" workspace/fraud_Detection_2pears/swop/swop*_profile.yaml
sed -i "s+<CURRENT-PATH>/examples/fraud-detection+$(pwd)/workspace/fraud_Detection_2pears+g" workspace/fraud_Detection_2pears/swop/swop*_profile.yaml
sed -i "s+<LICENSE-SERVER-ADDRESS>+${APLS_IP}+g" workspace/fraud_Detection_2pears/swop/swop*_profile.yaml
sed -i "s+<PROJECT-CERTS>+$(pwd)/workspace/fraud_Detection_2pears/cert+g" workspace/fraud_Detection_2pears/swop/swop*_profile.yaml
sed -i "s+<PROJECT-CACERTS>+$(pwd)/workspace/fraud_Detection_2pears/cert/ca/capath+g" workspace/fraud_Detection_2pears/swop/swop*_profile.yaml

echo "Creating volume and copying wheel..."
docker volume rm sl-cli-lib || true
docker volume create sl-cli-lib
docker container create --name helper -v sl-cli-lib:/data hello-world
docker cp lib/swarmlearning-client-py3-none-manylinux_2_24_x86_64.whl helper:/data
docker rm helper

echo "Starting Sentinel Node (SN)..."
./scripts/bin/run-sn -d --rm --name=sn1 --network=host-1-net --host-ip=${HOST_IP} --sentinel --sn-api-port=${SN_API_PORT} \
--key=workspace/fraud_Detection_2pears/cert/sn-1-key.pem --cert=workspace/fraud_Detection_2pears/cert/sn-1-cert.pem \
--capath=workspace/fraud_Detection_2pears/cert/ca/capath --apls-ip=${APLS_IP} \
-e http_proxy= -e https_proxy= -e HTTP_PROXY= -e HTTPS_PROXY=

echo "Starting Swarm Operator (SWOP)..."
./scripts/bin/run-swop -d --rm --name=swop1 --network=host-1-net --usr-dir=workspace/fraud_Detection_2pears/swop \
--profile-file-name=swop1_profile.yaml --sn-ip=${SN_IP} --sn-api-port=${SN_API_PORT} --key=workspace/fraud_Detection_2pears/cert/swop-1-key.pem \
--cert=workspace/fraud_Detection_2pears/cert/swop-1-cert.pem --capath=workspace/fraud_Detection_2pears/cert/ca/capath \
-e http_proxy= -e https_proxy= --apls-ip=${APLS_IP} \
--swop-uid 0

echo "Starting Swarm Command Interface (SWCI)..."
./scripts/bin/run-swci --rm --name=swci1 --network=host-1-net --usr-dir=workspace/fraud_Detection_2pears/swci \
--init-script-name=swci-init --key=workspace/fraud_Detection_2pears/cert/swci-1-key.pem \
--cert=workspace/fraud_Detection_2pears/cert/swci-1-cert.pem --capath=workspace/fraud_Detection_2pears/cert/ca/capath --apls-ip=${APLS_IP} < /dev/null 2>&1 | tee workspace/swci_output.log

echo ""
echo "======================================================"
echo "Deployment Complete for 2 Peers!"
echo "Check SN logs:         docker logs -f sn1"
echo "Check ML node logs:    docker logs -f <ml-node-container-id>"
echo "======================================================"
