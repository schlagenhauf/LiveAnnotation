# LiveAnnotation

## A tool for annotating live sensor data via shortcuts. Also allows to view and save camera input.

### TODO:
  * Write annotation data directly into video file
  * Make GStreamer handling more robust
  * Implement network video streaming
  * Improve visibility of plotted label markers
  * Improve performance

### Getting started:
You need the following packages (Ubuntu):
`sudo apt-get install gstreamer1.0-plugins-base gstreamer1.0-plugins-good
gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gir1.2-gstreamer-1.0
gstreamer1.0-plugins-base-apps gstreamer1.0-tools
gstreamer1.0-x libgstreamer-plugins-bad1.0-0 libgstreamer-plugins-base1.0-0
libgstreamer-plugins-good1.0-0 libgstreamer1.0-0
python-pyqtgraph python-qt4 python-qt4-gl python-gst-1.0`

### How to use:
Pipe your input data directly to the script:
`cat your_data_file.txt | ./liveannotation.py`
