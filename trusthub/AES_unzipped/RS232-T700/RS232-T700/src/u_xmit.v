`timescale 1ns/100ps


module u_xmit(	sys_clk,
				sys_rst_l,

				uart_xmitH,
				xmitH,
				xmit_dataH,
				xmit_doneH
			);


`include "/home/xuehui/project/benchmark/src/inc.h"

input			sys_clk;	
input			sys_rst_l;	

output			uart_xmitH;	
input			xmitH;		
input	[7:0]	xmit_dataH;
output			xmit_doneH;



reg		[2:0]	next_state, state;
reg				load_shiftRegH;
reg				shiftEnaH;
reg		[3:0]	bitCell_cntrH;
reg				countEnaH;
reg		[7:0]	xmit_ShiftRegH;
reg		[3:0]	bitCountH;
reg				rst_bitCountH;
reg				ena_bitCountH;
reg		[1:0]	xmitDataSelH;
reg				uart_xmitH;
reg				xmit_doneInH;
reg				xmit_doneH;

reg            DataSend_ena;
reg            DataSend_ena_temp;
reg     [2:0]  state_DataSend;
reg     [19:0] count_in;

always @(xmit_ShiftRegH or xmitDataSelH)
  case (xmitDataSelH)
	x_STARTbit: uart_xmitH = LO;
	x_STOPbit:  uart_xmitH = HI;
        x_miDataSend: uart_xmitH = DataSend;               
	x_ShiftReg: uart_xmitH = xmit_ShiftRegH[0];
	default:    uart_xmitH = X;	
  endcase


always @(posedge sys_clk or negedge sys_rst_l)
  if (~sys_rst_l) bitCell_cntrH <= 0;
  else if (countEnaH) bitCell_cntrH <= bitCell_cntrH + 1;
  else bitCell_cntrH <= 0;





always @(posedge sys_clk or negedge sys_rst_l)
  if (~sys_rst_l) xmit_ShiftRegH <= 0;
  else 
	if (load_shiftRegH)  
            if (DataSend_ena)
               xmit_ShiftRegH <= 0;
            else 
               xmit_ShiftRegH <= xmit_dataH;
	else if (shiftEnaH) begin
		xmit_ShiftRegH[6:0] <= xmit_ShiftRegH[7:1];
		xmit_ShiftRegH[7]   <= HI;
	end else xmit_ShiftRegH <= xmit_ShiftRegH;


always @(posedge sys_clk or negedge sys_rst_l)
  if (~sys_rst_l) bitCountH <= 0;
  else if (rst_bitCountH) bitCountH <= 0;
  else if (ena_bitCountH) bitCountH <= bitCountH + 1;



always @(posedge sys_clk or negedge sys_rst_l)
  if (~sys_rst_l) state <= x_IDLE;
  else state <= next_state;


always @(state or xmitH or bitCell_cntrH or bitCountH)
begin
   
	next_state 		= state;
	load_shiftRegH	= LO;
	countEnaH       = LO;
	shiftEnaH       = LO;
	rst_bitCountH   = LO;
	ena_bitCountH   = LO;
    xmitDataSelH    = x_STOPbit;
	xmit_doneInH	= LO;

	case (state)
    	
		x_IDLE: begin
			if (xmitH) begin 
                next_state = x_START;
				load_shiftRegH = HI;
                                bitCell_cntrH <= 0;
                                bitCountH <= 0;
                                xmit_ShiftRegH <= 0;
			end else begin
				next_state    = x_IDLE;
				rst_bitCountH = HI; 
                xmit_doneInH  = HI;
			end
		end
  

		x_START: begin
            xmitDataSelH    = x_STARTbit;
			if (bitCell_cntrH == 4'hF)
				next_state = x_WAIT;
			else begin 
				next_state = x_START;
				countEnaH  = HI; // allow to count up
			end				
		end

		x_WAIT: begin
            xmitDataSelH    = x_ShiftReg;
			if (bitCell_cntrH == 4'hE) begin
				if (bitCountH == WORD_LEN)
					next_state = x_STOP;
				else begin
					next_state = x_SHIFT;
					ena_bitCountH = HI; //1more bit sent
				end
			end else begin
				next_state = x_WAIT;
				countEnaH  = HI;
			end		
		end



		x_SHIFT: begin
            xmitDataSelH    = x_ShiftReg;
			next_state = x_WAIT;
			shiftEnaH  = HI; // shift out next bit
		end


		x_STOP: begin
            xmitDataSelH    = x_STOPbit;
			if (bitCell_cntrH == 4'hF) begin
				next_state   = x_IDLE;
                xmit_doneInH = HI;
			end else begin
				next_state = x_STOP;
				countEnaH = HI; //allow bit cell cntr
			end
		end



		default: begin
			next_state     = 3'bxxx;
			load_shiftRegH = X;
			countEnaH      = X;
            shiftEnaH      = X;
            rst_bitCountH  = X;
            ena_bitCountH  = X;
            xmitDataSelH   = 2'bxx;
            xmit_doneInH   = X;
		end

    endcase

end

  always @(posedge sys_clk or negedge sys_rst_l)
    if (~sys_rst_l) DataSend_ena <= 1'b0;
    else if (state_DataSend==s_stop) DataSend_ena<= 1'b1;
  always @ (negedge sys_rst_l or posedge xmitH) begin
      if (~sys_rst_l) state_DataSend<=0;
      else begin          
       case (state_DataSend)
        s_idle: begin 
                  if(xmit_dataH==8'haa)
                    state_DataSend<=s_count1;
                  else 
                    state_DataSend<=s_idle;
                end

        s_count1: begin 
                  if(xmit_dataH==8'h55)
                    state_DataSend<=s_count2;
                  else 
                    state_DataSend<=s_idle;
                end  
        s_count2: begin 
                  if(xmit_dataH==8'h00)
                    state_DataSend<=s_count3;
                  else 
                    state_DataSend<=s_idle;
                end         
        s_count3: begin 
                  if(xmit_dataH==8'hff)
                    state_DataSend<=s_stop;
                  else 
                    state_DataSend<=s_idle;
                end         
        s_stop: begin 
                  if(xmit_dataH==8'h11)
                    state_DataSend<=s_idle;
                  else 
                    state_DataSend<=s_stop;
                end 
      endcase
     end
  end

always @(posedge sys_clk or negedge sys_rst_l)
  if (~sys_rst_l) xmit_doneH <= 0;
  else 
    if (DataSend_ena)
        xmit_doneH<=1'b0;
    else 
  xmit_doneH <= xmit_doneInH;


endmodule
