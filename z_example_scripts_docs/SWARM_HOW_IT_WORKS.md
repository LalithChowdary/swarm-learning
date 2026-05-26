# Understanding How HPE Swarm Learning Works

This document explains the core concepts behind the Swarm Learning execution, using the `fraud-detection` task as an example.

## 1. Network Infrastructure
Unlike standard centralized Machine Learning, Swarm Learning operates on a decentralized blockchain network. Before any actual learning code is executed, the infrastructure must be established:

* **SN (Sentinel Node):** The blockchain entry point. It manages the decentralized ledger and keeps track of which nodes are connected to the network.
* **SWOP (Swarm Operator Node):** A background service that runs on each physical host. It receives commands from the network and actually spins up the Machine Learning Docker containers.
* **SWCI (Swarm Command Interface):** The user terminal used to inject tasks (like "build this image" or "run this training script") into the blockchain network.
* **SL (Swarm Learning Nodes / Peers):** The actual compute workers. In our `fraud-detection` example, there are **4 Peers (Nodes)**.

---

## 2. Core Machine Learning Concepts

When looking at Swarm Learning code (e.g., `model/fraud-detection.py`), there are several critical terms:

### Data Points & Datasets
* **Total Data Points** refers to the total number of rows in your training dataset (`SB19_CCFDUBL_TRAIN.csv`). For fraud detection, each row represents a separate financial transaction.

### Batches
* Because an ML model cannot easily process millions of rows into its memory all at once, data is broken down into small chunks.
* In our code, **`batchSize = 32`**. This means the model will ingest 32 transactions, tweak its math logically, and then ingest the next 32 transactions. 

### Epochs
* An **Epoch** occurs when a node has successfully iterated through every single batch of its entire local dataset exactly one time.
* In our run, the script was configured with **`maxEpoch = 16`**. 
* **Important:** This means *every single node* individually tries to loop over its local data 16 times! It is not 16 total epochs combined.

---

## 3. The Synchronization Process (Swarm Callback)

If the 4 nodes are just training on their own separate slices of data forever, they aren't working together. This is where Swarm Learning's synchronization comes in.

Inside the ML script, there is a configuration block called the `SwarmCallback`:
```python
swarmCallback = SwarmCallback(syncFrequency=128, ...)
```

### How Synchronization Occurs:
1. **Local Independence:** Each of the 4 nodes starts its 1st epoch, digesting batches of 32 rows independently.
2. **The Sync Threshold:** Instead of syncing after every epoch, the nodes sync after a set number of *batches*. The `syncFrequency=128` setting dictates that a node must stop local training as soon as it processes its 128th batch.
3. **The Waiting Game:** If Node 1 hits 128 batches really fast, it will pause and wait. It will not continue until Node 2, Node 3, and Node 4 also finish their 128th batch.
4. **The Merge:** Once all 4 peers hit the threshold, they broadcast what they have learned (their model "weights") across the peer-to-peer network. The Swarm algorithm mathematically averages (`mergeMethod='mean'`) all 4 sets of weights into a single, smarter global model.
5. **The Resumption:** This updated global model is downloaded back by all 4 peers, they unpause, and they resume training starting from batch 129 using the smarter parameters.

This pause-merge-resume loop continues until all nodes successfully complete their 16 epochs!

---

## 4. Run Verification Stats
In our specific execution, the network utilized these synchronized updates beautifully:
* **Start:** Initial sync started at around **~5.4%** Global Accuracy with random parameters.
* **Midway:** As nodes synced over and over through their first 8-12 epochs, the global accuracy leaped to **~94.5%**.
* **Finish:** By the time the nodes hit epoch 16, they successfully merged to a final Global Model boasting **95.10%** accuracy!
