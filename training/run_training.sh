#!/bin/bash

# Helper script to run training phases

# Function to run a phase
run_phase() {
    PHASE=$1
    CONFIG=$2
    RESUME=$3
    
    echo "------------------------------------------------"
    echo "Starting Phase $PHASE..."
    echo "Config: $CONFIG"
    if [ ! -z "$RESUME" ]; then
        echo "Resuming from: $RESUME"
        python3 train.py --config $CONFIG --resume_from $RESUME
    else
        python3 train.py --config $CONFIG
    fi
    echo "Phase $PHASE complete."
    echo "------------------------------------------------"
}

# Check arguments
if [ "$1" == "1" ]; then
    run_phase 1 "configs/phase1_burnin.yaml"
elif [ "$1" == "2" ]; then
    run_phase 2 "configs/phase2_advection.yaml" "checkpoints/phase1_burnin_best.pth"
elif [ "$1" == "3" ]; then
    run_phase 3 "configs/phase3_refinement.yaml" "checkpoints/phase2_advection_best.pth"
elif [ "$1" == "all" ]; then
    run_phase 1 "configs/phase1_burnin.yaml"
    run_phase 2 "configs/phase2_advection.yaml" "checkpoints/phase1_burnin_best.pth"
    run_phase 3 "configs/phase3_refinement.yaml" "checkpoints/phase2_advection_best.pth"
else
    echo "Usage: ./run_training.sh [1|2|3|all]"
    echo "  1: Run Phase 1 (Burn-in)"
    echo "  2: Run Phase 2 (Advection) - requires Phase 1 checkpoint"
    echo "  3: Run Phase 3 (Refinement) - requires Phase 2 checkpoint"
    echo "  all: Run all phases sequentially"
fi
