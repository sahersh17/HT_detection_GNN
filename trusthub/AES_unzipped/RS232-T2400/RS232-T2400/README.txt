1. This directory includes:

1.1 src
	---Codes for the micro-UART core, the test bench, and the Trojan

2.Trojan
Trojan Description
    The Trojan trigger is dependent on a rare branch within the receiver part of the micro-UART core. The Trojan is activated after the predefined branch (line 115 in the u_rec module) is taken three times and forces the rec_readyH output signal to be '0'.

Trojan Taxonomy
	Insertion phase: Design
	Abstraction level: Register-transfer level (RTL)
	Activation mechanism: Physical-condition-based
	Effects: Denial of service
	Physical characteristics: Functional 
