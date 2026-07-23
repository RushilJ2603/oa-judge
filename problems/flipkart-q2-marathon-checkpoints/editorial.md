# Marathon Checkpoints - Editorial

This problem asks us to find all checkpoints in a binary tree that have both a left and right child (two downstream checkpoints), and sum their values.
The tree is given as a list of paths from the root to each node. Each path is a string of 'L's and 'R's.

A simple way to solve this is to store all checkpoint values in a hash map where the key is the path string, and the value is the checkpoint integer. The root has an empty path string `""`.

After populating the hash map with all checkpoints, we iterate through each entry. For a node at path `P`, we check if the hash map contains both `P + "L"` and `P + "R"`. If both exist, the node has two downstream checkpoints, so we add its value to our total sum.
