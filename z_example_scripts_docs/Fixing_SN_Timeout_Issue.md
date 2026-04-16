# Troubleshooting and Fixing the 10-Second Web3 IPC Timeout in HPE Swarm Learning

## Background and Symptoms
When starting a Swarm Network (SN) node, especially on virtual machines or systems with low entropy, the container might crash shortly after printing `SMLETHNode: Enode list is empty: Node is standalone`.

The container logs will display an error sequence similar to this:
```text
Traceback (most recent call last):
  File "/usr/lib/python3.8/site-packages/web3/providers/ipc.py", line 218, in make_request
    raw_response += sock.recv(4096)
socket.timeout: timed out

...

web3.utils.threads.Timeout: 10 seconds
```

### The Root Cause
This error occurs because the HPE Swarm Learning container uses the Python `web3` library to communicate with the internal blockchain module (`GETH`) over an IPC socket. The `web3` library has a **hardcoded default timeout of 10 seconds** for these connections. On systems where `GETH` takes longer than 10 seconds to generate a new account and initialize keys, the Python script times out and crashes the node before GETH can finish.

There is no native Swarm Learning environment variable exported to change this specific third-party Python package setting. However, we can patch it using Docker volume mounts.

---

## Step-by-Step Fix

We circumvent this issue by extracting the Web3 IPC file from the Docker image, increasing the timeout locally, and injecting our modified file back into the container when it runs.

### Step 1: Extract the `ipc.py` file from the SN Docker Image
First, we spin up a temporary container from the SN image to copy the target Python file out to our local host machine.

Run the following command in your terminal from the Swarm Learning directory:
```bash
docker run --rm --entrypoint /bin/cat hub.myenterpriselicense.hpe.com/hpe/swarm-learning/sn:2.3.0 \
/usr/lib/python3.8/site-packages/web3/providers/ipc.py > workspace/ipc.py
```
*Note: Make sure the `workspace` directory exists (`mkdir -p workspace`). Adjust the image version (`sn:2.3.0`) if you are using a different release.*

### Step 2: Modify the Timeout Limit
Open the newly extracted file located at `./workspace/ipc.py` in an editor, or use `sed` to find and replace the default timeout.

Look for the `__init__` constructor of the `IPCProvider` class (around line 188):
```python
# Change this:
def __init__(self, ipc_path=None, testnet=False, timeout=10, *args, **kwargs):

# To this:
def __init__(self, ipc_path=None, testnet=False, timeout=120, *args, **kwargs):
```

Alternatively, run this automated `sed` command to perform the replacement instantly:
```bash
sed -i 's/timeout=10/timeout=120/g' workspace/ipc.py
```
*This updates the timeout to 120 seconds (2 minutes), providing ample time for the blockchain node to initialize securely.*

### Step 3: Inject the Modified File when starting the SN Node
Next, we need to instruct the SN run script (`./scripts/bin/run-sn`) to overwrite the default Python package with our modified file. 

The `run-sn` wrapper script accepts native Docker arguments such as the volume mount flag (`-v`). Append the volume mount instruction pointing our local file to the Python package path in the container.

Here is the updated command to start the SN Node (replace IP variables according to your environment):

```bash
export APLS_IP=192.168.64.6 
export HOST_IP=192.168.64.6 
export SN_IP=192.168.64.6 
export SN_API_PORT=30304

./scripts/bin/run-sn -d --rm --name=sn1 \
  --network=host-1-net \
  --host-ip=${HOST_IP} \
  --sentinel \
  --sn-api-port=${SN_API_PORT} \
  --key=workspace/fraud-detection/cert/sn-1-key.pem \
  --cert=workspace/fraud-detection/cert/sn-1-cert.pem \
  --capath=workspace/fraud-detection/cert/ca/capath \
  --apls-ip=${APLS_IP} \
  -v $(pwd)/workspace/ipc.py:/usr/lib/python3.8/site-packages/web3/providers/ipc.py
```
*Notice the appended line at the bottom: `-v $(pwd)/workspace/ipc.py:/usr/lib/python3.8/site-packages/web3/providers/ipc.py`*

### Step 4: Verify Successful Startup
Once the container is launched, monitor its logs:
```bash
docker logs -f sn1
```

You should see:
```text
2026-04-13 12:20:18,912 : swarm.SN : INFO : SMLETHNode: Starting GETH ... 
2026-04-13 12:20:29,261 : swarm.SN : WARNING : SMLETHNode: Enode list is empty: Node is standalone
```

At this point, **be patient**. It may sit at this stage for several minutes (no longer crashing at 10 seconds). Eventually, GETH will complete generating the cryptographic keys and the API server will start:

```text
2026-04-13 12:27:59,477 : swarm.blCnt : INFO : Setting up blockchain layer for the swarm node: FINISHED
2026-04-13 12:28:23,065 : swarm.blCnt : INFO : Starting SWARM-API-SERVER on port: 30304
```

Once you see `Starting SWARM-API-SERVER on port: 30304`, the fix successfully worked!