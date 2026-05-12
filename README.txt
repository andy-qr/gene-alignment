To use first type in your terminal:

cd <path_to_folder>
(for instance "cd c:/user/project/")

Then type :
pip install -r requirements.txt

Then you can run the program in your terminal using
python gui.py



To use the program select the taxon you want to align and the file with the raw data in it (can be txt (csv), ods or xslx)
Then choose the file format you want your results in and press run.


You can adjust the "Threshold" advanced setting if you feel gene recognition doesn't work as you intend.
Higher threshold means less genes will be accepted but with better precision.
Default is 0.25 and I don't recommend getting much lower.

Program is stocking "cache memory" to run much faster and with lesser use of the internet the more you run it.
If you want not to use it or to reset it you can in advanced settings.

You should be putting your files in a specific folder if you intend to analyze muliple analyzis of a single taxon, and you can then use the advanced setting "batch mode"
