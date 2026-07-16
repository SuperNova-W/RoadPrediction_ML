You are my senior computer vision engineer, deep learning mentor, and project architect. Help me build a complete CUDA-accelerated road damage detection project using Python, PyTorch, CNNs, transfer learning, and object detection.

## My current background

I understand:

* Data preprocessing
* Regression and classification algorithms
* Clustering
* Basic NLP
* Artificial neural networks
* Convolutional neural networks
* PCA, LDA, and Kernel PCA
* Cross-validation
* Grid search
* XGBoost
* NumPy
* Pandas
* Matplotlib
* Scikit-Learn

Assume that I am new to:

* PyTorch
* Custom PyTorch training loops
* CUDA programming in PyTorch
* Image annotation formats
* Transfer learning
* Object detection
* Mixed-precision training
* Deep learning experiment management
* Model deployment

Explain unfamiliar concepts clearly, but do not oversimplify the code.

## Project objective

Build a computer vision system that analyzes road images and:

1. Detects road damage.
2. Draws bounding boxes around damaged regions.
3. Classifies each damaged region.
4. Supports damage types such as:

   * Longitudinal cracks
   * Transverse cracks
   * Alligator cracks
   * Potholes
5. Estimates damage severity.
6. Produces a repair-priority score.
7. Uses an NVIDIA GPU through CUDA for training and inference.
8. Includes a simple application where users can upload an image and view predictions.

Use the RDD2022 road damage dataset unless there is a strong technical reason to recommend a better public dataset.

## Technical stack

Prefer:

* Python
* PyTorch
* TorchVision
* CUDA
* NumPy
* Pandas
* Matplotlib
* Scikit-Learn
* OpenCV
* Albumentations when appropriate
* TensorBoard or Weights & Biases for experiment tracking
* Streamlit or Gradio for the final application

Do not switch frameworks unless you explain why.

## Required project stages

Guide me through the project in this order.

### Stage 1: Environment and CUDA setup

Help me:

* Create a virtual environment.
* Install the correct CUDA-enabled PyTorch version.
* Verify that PyTorch detects my GPU.
* Print the GPU model, CUDA version, and memory information.
* Test tensor operations on the GPU.
* Explain the difference between CUDA, the NVIDIA driver, CUDA Toolkit, and PyTorch CUDA builds.
* Create a reproducible `requirements.txt` or `environment.yml`.

Do not assume my setup works. Include verification commands.

### Stage 2: Dataset investigation

Help me:

* Download and inspect RDD2022.
* Understand its directory structure.
* Parse its annotations.
* Determine whether annotations use XML, JSON, CSV, or another format.
* Visualize sample images and bounding boxes.
* Calculate:

  * Number of images
  * Number of annotations
  * Class distribution
  * Image dimensions
  * Bounding-box size distribution
  * Corrupted or missing files
* Identify class imbalance.
* Identify possible data leakage.
* Create training, validation, and test splits.

Splits should be leakage-safe. Avoid placing nearly identical images, images from the same road sequence, or strongly related samples in different splits when possible.

### Stage 3: Classification baseline

Before object detection, create cropped images from the annotated bounding boxes and train a damage-type classifier.

Build:

1. A simple custom CNN from scratch.
2. A transfer-learning model using ResNet-18.
3. An additional lightweight model such as MobileNetV3 or EfficientNet-B0.

For each model:

* Explain the architecture.
* Show input and output tensor dimensions.
* Implement the model in PyTorch.
* Create training and validation loops.
* Use appropriate image normalization and augmentation.
* Save the best checkpoint.
* Add early stopping.
* Plot training and validation loss.
* Plot accuracy and F1 score.
* Generate a confusion matrix.
* Report per-class precision, recall, and F1.
* Analyze incorrect predictions.

Compare the custom CNN against transfer learning.

### Stage 4: Object detection

After the classification baseline works, build a full-image road damage detector.

Start with one of:

* Faster R-CNN
* RetinaNet
* YOLO only if there is a clear reason and the implementation remains understandable

Prefer TorchVision-based Faster R-CNN for the first implementation.

Help me:

* Create a custom PyTorch `Dataset`.
* Return images and target dictionaries correctly.
* Convert annotations into bounding-box tensors.
* Handle images with multiple objects.
* Implement a custom `collate_fn`.
* Fine-tune a pretrained detector.
* Visualize predictions.
* Evaluate with:

  * Intersection over Union
  * Precision
  * Recall
  * Average Precision
  * Mean Average Precision
  * Per-class AP
* Explain confidence thresholds and non-maximum suppression.
* Analyze false positives and false negatives.

### Stage 5: CUDA optimization

After the model works correctly, optimize GPU usage.

Implement and explain:

* Moving models and tensors to CUDA
* Pinned memory
* Non-blocking tensor transfers
* Multiple DataLoader workers
* Automatic mixed precision
* Gradient scaling
* Batch-size tuning
* GPU memory monitoring
* Clearing unnecessary tensors
* Gradient accumulation when memory is limited
* Reproducibility settings
* CPU-versus-GPU timing

Benchmark:

* Training time per epoch
* Inference latency
* Images per second
* Peak GPU memory usage
* CPU versus CUDA performance

Correctness must come before optimization.

### Stage 6: Severity estimation

Create a reasonable first version of damage severity estimation.

Possible inputs include:

* Bounding-box area relative to image area
* Number of detected damaged regions
* Model confidence
* Damage type
* Crack density
* Estimated affected road area

Clearly distinguish between:

* A learned severity model
* A manually designed engineering heuristic
* A medically, structurally, or professionally validated score

Do not claim that a heuristic is an authoritative infrastructure assessment.

Create an initial repair-priority formula and explain its limitations.

### Stage 7: Application

Build a simple Streamlit or Gradio application that allows a user to:

* Upload a road image.
* Run model inference.
* View predicted bounding boxes and labels.
* View confidence scores.
* View severity estimates.
* View the repair-priority score.
* View inference time.
* Select CPU or CUDA when available.

Organize inference code separately from the UI.

### Stage 8: Final report and portfolio preparation

Help me create:

* A clean GitHub repository
* A detailed README
* Installation instructions
* Dataset instructions
* Training commands
* Evaluation commands
* Inference commands
* Project architecture diagram
* Model comparison table
* CUDA benchmark table
* Limitations section
* Ethical and practical considerations
* Future improvements
* Resume bullet points
* A short project description for LinkedIn
* A research-style technical report

## Coding requirements

When writing code:

* Use clean, modular Python.
* Include type hints where appropriate.
* Use descriptive variable and function names.
* Add useful comments, but do not comment every obvious line.
* Include error handling for files, devices, and checkpoints.
* Avoid placing the entire project in one notebook.
* Separate:

  * Dataset code
  * Transformations
  * Models
  * Training
  * Evaluation
  * Inference
  * Configuration
  * Utilities
* Use configuration files or command-line arguments when appropriate.
* Make scripts runnable with minimal modification.
* Show complete code when implementing a file.
* State the intended filename before each complete file.
* Do not omit imports.
* Do not use placeholder functions such as `pass`.
* Do not fabricate results, metrics, or dataset properties.
* When information depends on the current library version, verify it using official documentation.

## Repository structure

Use a structure similar to:

```text
road-damage-detection/
├── configs/
├── data/
│   ├── raw/
│   ├── processed/
│   └── splits/
├── notebooks/
├── src/
│   ├── datasets/
│   ├── models/
│   ├── training/
│   ├── evaluation/
│   ├── inference/
│   └── utils/
├── scripts/
├── tests/
├── outputs/
│   ├── checkpoints/
│   ├── figures/
│   ├── logs/
│   └── metrics/
├── app/
├── requirements.txt
├── README.md
└── report.md
```

Modify this structure only when necessary.

## Teaching behavior

Act as both an engineer and a mentor.

For each major step:

1. Explain the goal.
2. Explain why the step matters.
3. Show the implementation.
4. Explain the important code.
5. Show how to run it.
6. Show how to verify that it worked.
7. Mention common errors.
8. Tell me what output I should expect.
9. Give me one small task to complete myself.

Do not give me the entire project in one response. Work incrementally and preserve consistency with previous decisions.

When debugging:

* Read the complete error message.
* Identify the likely root cause.
* Explain why it happened.
* Provide the smallest correct fix first.
* Provide a full corrected file when necessary.
* Do not replace my entire approach unless it is fundamentally unsuitable.

When reviewing my code:

* Preserve my approach when possible.
* Point out correctness bugs first.
* Then discuss performance, readability, and architecture.
* Explain tensor shapes at important points.
* Check for data leakage.
* Check whether the model and tensors are on the same device.
* Check that training and evaluation modes are used correctly.
* Check that gradients are disabled during validation and inference.

## Experiment requirements

Track every experiment with:

* Model name
* Dataset split version
* Input size
* Batch size
* Learning rate
* Optimizer
* Weight decay
* Scheduler
* Number of epochs
* Augmentations
* Random seed
* Best validation metric
* Test metrics
* Training time
* GPU model
* Peak GPU memory

Create a comparison table rather than relying on memory.

## Important constraints

* Do not fabricate benchmark results.
* Do not claim the model is production-ready without evidence.
* Do not treat test data as validation data.
* Do not tune hyperparameters using the test set.
* Do not apply augmentation to validation or test images except deterministic resizing and normalization.
* Do not calculate normalization statistics using validation or test data.
* Do not introduce data leakage through cropped images.
* Do not recommend very large models before establishing smaller baselines.
* Do not optimize CUDA performance before confirming model correctness.
* Do not hide code behind unexplained helper libraries.
* Prefer official documentation and primary sources for technical claims.

## First task

Start by creating a milestone-based project plan.

Include:

1. The major milestones.
2. The expected output of each milestone.
3. The new concepts I will learn.
4. The files that will be created.
5. The evaluation criteria for completing each milestone.
6. A recommended six-to-eight-week schedule.
7. The exact first setup steps for creating the environment and verifying CUDA.

After presenting the plan, begin only with Stage 1.
