# Swarm Learning Execution Breakdown

This document provides a detailed breakdown of your `fraud-detection` Swarm Learning network run. Based on the logs, your environment successfully initialized a decentralized network of 4 nodes, compiled a custom TensorFlow environment, and successfully collaboratively trained a high-accuracy model.

---

## 🏗️ 1. Infrastructure Setup & Network Initialization
Before any training could occur, the Swarm Learning scripts laid the groundwork:

*   **Certificate Generation**: The script successfully generated self-signed RSA certificates for all of the Swarm Learning internal nodes:
    *   `CA-1` (Certificate Authority)
    *   `SN-1` (Sentinel Node)
    *   `SL-1` (Swarm Learning Node)
    *   `SWCI-1` (Swarm Command Interface)
    *   `SWOP-1` (Swarm Operator Node)
*   **Node Bootstrapping**:
    *   The **Sentinel Node (SN1)** was started. It functions as the entry point and the leader for the blockchain-based decentralized registry.
    *   The **Swarm Operator (SWOP1)** was started, connecting to the SN.
    *   The **Swarm Command Interface (SWCI1)** was brought up, which acts as the interactive CLI terminal driving the operations.

---

## 📦 2. Pre-requisite Build Phase (`user_env_tf_build_task`)
Training requires an identical software environment across all decentralized peer nodes.

The SWCI registered a `MAKE_USER_CONTAINER` task which:
1.  Pulled the `tensorflow/tensorflow:2.7.0` base image.
2.  Installed critical deep learning dependencies: `keras`, `matplotlib`, `opencv-python`, `pandas`, `protobuf==3.15.6`.
3.  Installed the HPE Swarm Learning Python client `wheel` file that allows the ML training script to talk to the Swarm network.
4.  Created a master image outcome named `user-env-tf2.7.0-swop`.

**Status**: The build was completed successfully at `11:36:07`.

---

## 🚀 3. The Decentralized Training Phase (`swarm_fd_task`)
Once the environment was built, the actual Machine Learning commenced.

### Run Configuration
- **Script Executed**: `model/fraud-detection.py`
- **Total Nodes Involved**: **4 Peer Nodes**
- **Total Rounds (Epochs)**: **16 Maximum Epochs**
- **Minimum Peers Needed**: 4

### The Training Sequence & Performance
During the span of ~6 minutes, the logs show the CLI polling the Swarm network (`PERFDATA` command) to extract real-time training aggregated stats. Here is the step-by-step progress of how your model improved:

| Sync Snapshot | Max Epochs Reached by a Node | Global Metric (Accuracy) | Global Loss | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Start (0%)** | `0 / 16` | **~5.44%** `(0.0544)` | **0.7940** | The network has just initialized. Initial random weights are shared across all 4 nodes resulting in low baseline accuracy. |
| **Sync 1 (~50%)** | `8 / 16` (Node 3) | **~93.92%** `(0.9392)` | **0.3012** | Massive leap! As nodes locally train and share parameters across the network, the global accuracy rockets over 90% and loss is cut by more than half. |
| **Sync 2 (~75%)** | `12 / 16` (Node 3) | **~94.58%** `(0.9458)` | **0.2572** | The network is fine-tuning the model. Model loss continues to decrease steadily across all peers. |
| **Final (~100%)** | `16 / 16` (Node 3) | **~95.10%** `(0.9510)` | **0.2274** | **Peak Performance.** Node 3 completes all 16 epochs, and the aggregated final model yields a fantastic 95% global accuracy. |

---

## ✅ 4. Teardown and Graceful Exit
After the taskrunner marked the training as `COMPLETE` at `11:42:48`:
1.  The network invoked a `SLEEP 15` command—a 15-second grace period strictly meant for the Machine Learning peers to safely save their finalized model weights (`.h5` files or similar) to your local disk mount (`/tmp/test/`).
2.  The `RESET CONTRACT` command successfully deactivated the smart contracts orchestrating the tasks.
3.  The SWCI node executed the `EXIT` sequence, and the containers were cleaned up locally.

## Summary
The training went **flawlessly**. Exactly **4 Swarm compute nodes** successfully merged their models together over the course of **16 total epochs**, bringing the initial ~5% baseline accuracy up to an excellent **95.10% global accuracy!**
