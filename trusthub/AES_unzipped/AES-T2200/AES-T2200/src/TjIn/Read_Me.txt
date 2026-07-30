source run_tjfree : You can open the script and change the target file name (aes_synth_opt.v to aes_synth.v) based on which trojan you prefer

source run_tj : You can open the script and change the target file name (aes_synth_opt.v to aes_synth.v) based on which trojan you prefer



tbTOP.v - tests only the aes_128 module
----------------------
If the output is wrong, the test bench will display an error message. But the output in this trojan is not modified hence it will always show it as 'Good'.

test_aes_128.v - tests only the aes_128 module
----------------------
This file is the main test bench. 
It is self-checked. It feeds input data to the core and compare the correct result with the output of the core. 
If the output is wrong, the test bench will display an error message.
