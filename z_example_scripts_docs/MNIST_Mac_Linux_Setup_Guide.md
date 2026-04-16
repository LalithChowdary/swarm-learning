# MNIST Swarm Learning Setup: macOS + Linux VM

This guide provides a clean, step-by-step process for running the Swarm Learning MNIST example across a macOS host and a Linux VM. 

## The Core Concept: Resolving Path Mismatches
Swarm Learning uses a unified task definition (`swarm_mnist_task.yaml`) that is sent to both machines to mount the Machine Learning (ML) model. Because macOS uses `/Users/...` and Linux uses `/home/...`, passing a local path from one will cause the other to fail. 

**The Solution:** We will copy the ML model to a universal path (`/tmp/swarm-model`) that looks exactly the same on both machines.

---

### Step 1: Clean Up Previous State
Run these commands to ensure we are starting with a completely clean slate. 

**On macOS (10.79.99.58):**
```bash
cd ~/code/HPE_CPP3/code/1/swarm-learning
./scripts/bin/stop-swarm || true
docker rm -f sn1 swop1 swci1 || true
docker network rm host-1-net || true
rm -rf workspace
```

**On Linux VM (192.168.64.6):**
```bash
# Go to your swarm-learning folder
cd ~/Desktop/HPE/swarm-learning
./scripts/bin/stop-swarm || true
docker rm -f sn2 swop2 || true
docker network rm host-2-net || true
rm -rf workspace
```

---

### Step 2: Create the Universal Model Directory
We will copy the model code to `/tmp/swarm-model` on both machines.

**On macOS:**
```bash
rm -rf /tmp/swarm-model
cp -r examples/mnist/model /tmp/swarm-model
```

**On Linux VM:**
```bash
rm -rf /tmp/swarm-model
cp -r examples/mnist/model /tmp/swarm-model
```

---

### Step 3: Setup Workspaces and Generate Certificates
Create the workspaces and generate the initial keys. 

**On macOS (Host 1):**
```bash
mkdir workspace
cp -r examples/mnist workspace/
cp -r examples/utils/gen-cert workspace/mnist/
./workspace/mnist/gen-cert -e mnist -i 1
```

**On Linux VM (Host 2):**
```bash
mkdir workspace
cp -r examples/mnist workspace/
cp -r examples/utils/gen-cert workspace/mnist/
./workspace/mnist/gen-cert -e mnist -i 2
```

---

### Step 4: Swap CA Certificates
The swarm nodes need to trust each other. We use `scp` to swap the CA keys.

**On macOS:**
```bash
# Pull the cert from the Linux VM (replace <USER> with your Linux VM username, e.g., lalith)
scp lalith@192.168.64.6:~/Desktop/HPE/swarm-learning/workspace/mnist/cert/ca/capath/ca-2-cert.pem workspace/mnist/cert/ca/capath/
```

**On Linux VM:**
```bash
# Pull the cert from the Mac (replace <USER> with your Mac username, e.g., lalith)
scp lalith@10.79.99.58:~/code/HPE_CPP3/code/1/swarm-learning/workspace/mnist/cert/ca/capath/ca-1-cert.pem workspace/mnist/cert/ca/capath/
```

---

### Step 5: Docker Networks & Library Volumes
Create the networks and inject the Swarm Learning client wheel into a shared volume.

**On macOS:**
```bash
docker network create host-1-net
docker volume rm sl-cli-lib || true
docker volume create sl-cli-lib
docker container create --name helper -v sl-cli-lib:/data hello-world
docker cp lib/swarmlearning-client-py3-none-manylinux_2_24_x86_64.whl helper:/data
docker rm helper
```

**On Linux VM:**
```bash
docker network create host-2-net
docker volume rm sl-cli-lib || true
docker volume create sl-cli-lib
docker container create --name helper -v sl-cli-lib:/data hello-world
docker cp lib/swarmlearning-client-py3-none-manylinux_2_24_x86_64.whl helper:/data
docker rm helper
```

---

### Step 6: Configure Swarm Profiles
Here, we configure the local `swop_profile.yaml` for each individual machine. Importantly, we tell the task definition to use our universal `/tmp/swarm-model` path.

**On macOS:**
```bash
export PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin:$PATH"
export APLS_IP=192.168.64.6
export HOST_1_IP=10.79.99.58

# Point the global task definition to our universal path:
sed -i "s+<PROJECT-MODEL>+/tmp/swarm-model+g" workspace/mnist/swci/taskdefs/swarm_mnist_task.yaml

# Configure the local Mac Operator Profile
sed -i "s+<SWARM-NETWORK>+host-1-net+g" workspace/mnist/swop/swop1_profile.yaml
sed -i "s+<HOST_ADDRESS>+${HOST_1_IP}+g" workspace/mnist/swop/swop1_profile.yaml
sed -i "s+<LICENSE-SERVER-ADDRESS>+${APLS_IP}+g" workspace/mnist/swop/swop1_profile.yaml
sed -i "s+<PROJECT>+$(pwd)/workspace/mnist+g" workspace/mnist/swop/swop1_profile.yaml
sed -i "s+<PROJECT-CERTS>+$(pwd)/workspace/mnist/cert+g" workspace/mnist/swop/swop1_profile.yaml
sed -i "s+<PROJECT-CACERTS>+$(pwd)/workspace/mnist/cert/ca/capath+g" workspace/mnist/swop/swop1_profile.yaml
```

**On Linux VM:**
```bash
export APLS_IP=192.168.64.6
export HOST_2_IP=192.168.64.6

# Configure the local Linux Operator Profile
sed -i "s+<SWARM-NETWORK>+host-2-net+g" workspace/mnist/swop/swop2_profile.yaml
sed -i "s+<HOST_ADDRESS>+${HOST_2_IP}+g" workspace/mnist/swop/swop2_profile.yaml
sed -i "s+<LICENSE-SERVER-ADDRESS>+${APLS_IP}+g" workspace/mnist/swop/swop2_profile.yaml
sed -i "s+<PROJECT>+$(pwd)/workspace/mnist+g" workspace/mnist/swop/swop2_profile.yaml
sed -i "s+<PROJECT-CERTS>+$(pwd)/workspace/mnist/cert+g" workspace/mnist/swop/swop2_profile.yaml
sed -i "s+<PROJECT-CACERTS>+$(pwd)/workspace/mnist/cert/ca/capath+g" workspace/mnist/swop/swop2_profile.yaml
```

---

### Step 7: Run Swarm Network (SN) Nodes
(Run as single lines)

**1. On macOS (Start Sentinel Node):**
```bash
./scripts/bin/run-sn -d --rm --name=sn1 --network=host-1-net --host-ip=10.79.99.58 --sentinel --sn-p2p-port=30303 --sn-api-port=30304 --key=workspace/mnist/cert/sn-1-key.pem --cert=workspace/mnist/cert/sn-1-cert.pem --capath=workspace/mnist/cert/ca/capath --apls-ip=192.168.64.6
```

**2. On Linux VM (Start SN2):**
```bash
./scripts/bin/run-sn -d --rm --name=sn2 --network=host-2-net --host-ip=192.168.64.6 --sentinel-ip=10.79.99.58 --sn-p2p-port=30303 --sn-api-port=30304 --key=workspace/mnist/cert/sn-2-key.pem --cert=workspace/mnist/cert/sn-2-cert.pem --capath=workspace/mnist/cert/ca/capath --apls-ip=192.168.64.6
```

---

### Step 8: Run Swarm Operators (SWOP)
(Run as single lines)

**On macOS:**
```bash
./scripts/bin/run-swop -d --rm --name=swop1 --network=host-1-net --sn-ip=10.79.99.58 --sn-api-port=30304 --usr-dir=workspace/mnist/swop --profile-file-name=swop1_profile.yaml --key=workspace/mnist/cert/swop-1-key.pem --cert=workspace/mnist/cert/swop-1-cert.pem --capath=workspace/mnist/cert/ca/capath -e http_proxy= -e https_proxy= --apls-ip=192.168.64.6
```

**On Linux VM:**
```bash
./scripts/bin/run-swop -d --rm --name=swop2 --network=host-2-net --sn-ip=192.168.64.6 --sn-api-port=30304 --usr-dir=workspace/mnist/swop --profile-file-name=swop2_profile.yaml --key=workspace/mnist/cert/swop-2-key.pem --cert=workspace/mnist/cert/swop-2-cert.pem --capath=workspace/mnist/cert/ca/capath -e http_proxy= -e https_proxy= --apls-ip=192.168.64.6
```

---

### Step 9: Trigger Training (SWCI)
Run the interface command from the macOS machine to orchestrate and begin the training process. Since the task definition now uses `/tmp/swarm-model` and both machines have that folder with the correct contents, you won't encounter container creation failures.

**On macOS:**
```bash
./scripts/bin/run-swci --rm --name=swci1 --network=host-1-net --usr-dir=workspace/mnist/swci --init-script-name=swci-init --key=workspace/mnist/cert/swci-1-key.pem --cert=workspace/mnist/cert/swci-1-cert.pem --capath=workspace/mnist/cert/ca/capath -e http_proxy= -e https_proxy= --apls-ip=192.168.64.6
```

**To monitor the process:**
- Check Sentinel logs: `docker logs -f sn1` or `sn2`
- Check SWOP logs: `docker logs -f swop1` or `swop2`
- Check ML Nodes: Once `swci` triggers the run, `docker ps` will show dynamically created ML containers. Use `docker logs -f <container_name>` to see TensorFlow output!