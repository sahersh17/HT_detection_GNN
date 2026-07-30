// Verilog HDL NetList 
//   timeStamp 2010 6 10 15 27 5 
//   author "Avanti Corporation."
//   program "A2Hdl" 
//   design library: uart_ori
//   cell name     : uart_scan.CEL (version 1)
`timescale 1ns/100ps

module uart ( sys_clk, sys_rst_l, uart_XMIT_dataH, xmitH, xmit_dataH,
        xmit_doneH, uart_REC_dataH, rec_dataH, rec_readyH, test_mode, test_se,
        test_si, test_so,ena );
    
   input [7:0] xmit_dataH ;
    output [7:0] rec_dataH ;
    input sys_clk ;
    input sys_rst_l ;
    input xmitH ;
    input uart_REC_dataH ;
    input test_mode ;
    input test_se ;
    input test_si ;
    input ena ;
    output uart_XMIT_dataH ;
    output xmit_doneH ;
    output rec_readyH ;
    output test_so ;
    wire [7:0] rec_dataH_temp ;
    wire \test_point/TM ;
    wire n23 ;
    wire n151 ;
    wire [7:0] rec_dataH_rec ;
    wire n8 ;
    wire n22 ;
    wire n18 ;
    wire n144 ;
    wire n21 ;
    wire n137 ;
    wire n20 ;
    wire n130 ;
    wire n19 ;
    wire n123 ;
    wire n17 ;
    wire n116 ;
    wire iRECEIVER_state_1_ ;
    wire n248 ;
    wire n15 ;
    wire n238 ;
    wire n245 ;
    wire n9 ;
    wire iRECEIVER_N28 ;
    wire n12 ;
    wire iRECEIVER_recd_bitCntrH_3_ ;
    wire n109 ;
    wire n243 ;
    wire n11 ;
    wire iRECEIVER_recd_bitCntrH_0_ ;
    wire n106 ;
    wire iRECEIVER_N26 ;
    wire n10 ;
    wire iRECEIVER_recd_bitCntrH_1_ ;
    wire n103 ;
    wire iRECEIVER_N27 ;
    wire n7 ;
    wire iRECEIVER_recd_bitCntrH_2_ ;
    wire n100 ;
    wire n242 ;
    wire n239 ;
    wire n3 ;
    wire n257 ;
    wire iXMIT_state_2_ ;
    wire iXMIT_state_0_ ;
    wire n2 ;
    wire iXMIT_state_1_ ;
    wire n26 ;
    wire n43 ;
    wire n42 ;
    wire n211 ;
    wire n67 ;
    wire n68 ;
    wire iXMIT_next_state_0_ ;
    wire n267 ;
    wire n80 ;
    wire n91 ;
    wire n83 ;
    wire n264 ;
    wire n266 ;
    wire n265 ;
    wire iRECEIVER_bitCell_cntrH_3_ ;
    wire iRECEIVER_bitCell_cntrH_2_ ;
    wire iRECEIVER_bitCell_cntrH_1_ ;
    wire n255 ;
    wire n79 ;
    wire iRECEIVER_state_0_ ;
    wire n93 ;
    wire n241 ;
    wire n244 ;
    wire n256 ;
    wire n85 ;
    wire n88 ;
    wire n94 ;
    wire iRECEIVER_state_2_ ;
    wire n92 ;
    wire iRECEIVER_N20 ;
    wire iRECEIVER_N17 ;
    wire iRECEIVER_N21 ;
    wire iRECEIVER_N18 ;
    wire iRECEIVER_N22 ;
    wire iRECEIVER_N19 ;
    wire iRECEIVER_N23 ;
    wire n89 ;
    wire n86 ;
    wire n87 ;
    wire iRECEIVER_rec_datH ;
    wire iRECEIVER_next_state_0_ ;
    wire n84 ;
    wire n81 ;
    wire n82 ;
    wire iRECEIVER_next_state_1_ ;
    wire iRECEIVER_next_state_2_ ;
    wire n77 ;
    wire iRECEIVER_rec_readyInH ;
    wire iXMIT_bitCell_cntrH_2_ ;
    wire iXMIT_bitCell_cntrH_1_ ;
    wire iXMIT_bitCell_cntrH_3_ ;
    wire n75 ;
    wire n254 ;
    wire n57 ;
    wire n62 ;
    wire n72 ;
    wire n246 ;
    wire n66 ;
    wire n74 ;
    wire n54 ;
    wire iXMIT_bitCell_cntrH_0_ ;
    wire n61 ;
    wire n65 ;
    wire n73 ;
    wire n71 ;
    wire iXMIT_N26 ;
    wire iXMIT_N23 ;
    wire iXMIT_N27 ;
    wire iXMIT_N24 ;
    wire iXMIT_N28 ;
    wire iXMIT_N25 ;
    wire iXMIT_N29 ;
    wire n253 ;
    wire iXMIT_bitCountH_0_ ;
    wire iXMIT_bitCountH_1_ ;
    wire iXMIT_bitCountH_2_ ;
    wire n69 ;
    wire n53 ;
    wire n63 ;
    wire n64 ;
    wire n44 ;
    wire n28 ;
    wire n60 ;
    wire iXMIT_next_state_2_ ;
    wire n58 ;
    wire n55 ;
    wire n56 ;
    wire n51 ;
    wire n52 ;
    wire n47 ;
    wire n46 ;
    wire n50 ;
    wire n252 ;
    wire n223 ;
    wire n49 ;
    wire iXMIT_N44 ;
    wire n220 ;
    wire n48 ;
    wire iXMIT_N45 ;
    wire n217 ;
    wire iXMIT_bitCountH_3_ ;
    wire n45 ;
    wire iXMIT_N46 ;
    wire n214 ;
    wire n29 ;
    wire iXMIT_xmit_ShiftRegH_7_ ;
    wire n41 ;
    wire n258 ;
    wire n208 ;
    wire n39 ;
    wire iXMIT_xmit_ShiftRegH_6_ ;
    wire n259 ;
    wire n205 ;
    wire n37 ;
    wire iXMIT_xmit_ShiftRegH_5_ ;
    wire n260 ;
    wire n202 ;
    wire n35 ;
    wire iXMIT_xmit_ShiftRegH_4_ ;
    wire n261 ;
    wire n199 ;
    wire n33 ;
    wire iXMIT_xmit_ShiftRegH_3_ ;
    wire n262 ;
    wire n196 ;
    wire n31 ;
    wire iXMIT_xmit_ShiftRegH_2_ ;
    wire n263 ;
    wire n193 ;
    wire n27 ;
    wire iXMIT_xmit_ShiftRegH_1_ ;
    wire n190 ;
    wire n25 ;
    wire n165 ;
    wire n24 ;
    wire n158 ;
    wire iCTRL ;
    wire xmit_doneH_temp ;
    wire iXMIT_CRTL ;
    wire RECEIVER_state_CTRL ;
    wire iRECEIVER_state_CTRL ;
    wire iXMIT_state_CTRL ;
    wire iXMIT_N_CTRL_1_ ;
    wire iXMIT_N_CTRL_2_ ;
    wire iXMIT_xmit_CTRL ;
    wire \test_point/DOUT ;
    wire n371 ;
    wire n370 ;
    wire iRECEIVER_rec_datSyncH ;
    wire n281 ;
    wire n250 ;
    wire n249 ;
    wire iRECEIVER_bitCell_cntrH_0_ ;
    wire iXMIT_xmit_doneInH ;
    wire n247 ;
    wire iXMIT_next_state_1_ ;
    wire n251 ;
    wire n275 ;
    wire n274 ;
    wire n273 ;
    wire n272 ;
    wire n271 ;
    wire n270 ;
    wire n269 ;
    wire n268 ;
    assign test_so = rec_dataH_temp[7] ;
    assign \test_point/TM = test_mode ;
    OAI21X1  U32 (.A0(n257), .A1(n26), .B0(n27), .Y(n190));
    OAI21X1  U35 (.A0(n263), .A1(n26), .B0(n31), .Y(n193));
    OAI21X1  U38 (.A0(n26), .A1(n262), .B0(n33), .Y(n196));
    OAI21X1  U41 (.A0(n26), .A1(n261), .B0(n35), .Y(n199));
    OAI21X1  U44 (.A0(n26), .A1(n260), .B0(n37), .Y(n202));
    OAI21X1  U47 (.A0(n26), .A1(n259), .B0(n39), .Y(n205));
    OAI21X1  U50 (.A0(n26), .A1(n258), .B0(n41), .Y(n208));
    OAI21X1  U91 (.A0(n239), .A1(n72), .B0(n73), .Y(n71));
    OAI21X1  U106 (.A0(n238), .A1(n245), .B0(n77), .Y(iRECEIVER_rec_readyInH));
    OAI21X1  U3 (.A0(iXMIT_state_2_), .A1(iXMIT_state_1_), .B0(n2), .Y(
        uart_XMIT_dataH));
    OAI21X1  U14 (.A0(n238), .A1(n245), .B0(n15), .Y(n9));
    OAI21X1  U15 (.A0(iRECEIVER_state_1_), .A1(n248), .B0(n238), .Y(n15));
    NOR2X1  U217 (.A(n268), .B(n251), .Y(n269));
    NOR2X1  U221 (.A(n270), .B(n247), .Y(n271));
    NOR2X1  U225 (.A(n272), .B(n249), .Y(n273));
    NOR2X1  U229 (.A(n274), .B(n250), .Y(n275));
    NOR2X1  U57 (.A(n44), .B(n28), .Y(n29));
    NOR2X1  U66 (.A(n51), .B(n47), .Y(n46));
    NOR2X1  U67 (.A(n52), .B(n53), .Y(n47));
    NOR2X1  U94 (.A(n75), .B(iXMIT_bitCell_cntrH_0_), .Y(n61));
    NOR2X1  U95 (.A(n246), .B(n239), .Y(n54));
    NOR2X1  U97 (.A(n246), .B(iXMIT_state_0_), .Y(n66));
    NOR2X1  U100 (.A(n242), .B(n57), .Y(n62));
    NOR2X1  U101 (.A(n254), .B(n75), .Y(n57));
    NOR2X1  U111 (.A(n238), .B(iRECEIVER_state_0_), .Y(n8));
    NOR2X1  U120 (.A(iRECEIVER_recd_bitCntrH_2_), .B(
        iRECEIVER_recd_bitCntrH_1_), .Y(n89));
    NOR2X1  U123 (.A(n241), .B(n245), .Y(n80));
    AOI21X1  U56 (.A0(iXMIT_xmit_ShiftRegH_7_), .A1(n44), .B0(n29), .Y(n42));
    AOI21X1  U77 (.A0(n239), .A1(iXMIT_state_2_), .B0(n28), .Y(n44));
    AOI21X1  U80 (.A0(iXMIT_state_1_), .A1(n65), .B0(n66), .Y(n63));
    AOI21X1  U82 (.A0(n66), .A1(n57), .B0(n62), .Y(n68));
    AOI21X1  U114 (.A0(iRECEIVER_state_1_), .A1(n85), .B0(n248), .Y(n84));
    AOI21X1  U129 (.A0(n88), .A1(n245), .B0(iRECEIVER_state_2_), .Y(n94));
    AOI21X1  U135 (.A0(n79), .A1(iRECEIVER_state_0_), .B0(n241), .Y(n93));
    AOI21X1  U4 (.A0(iXMIT_state_2_), .A1(iXMIT_state_0_), .B0(n3), .Y(n2));
    AOI21X1  U5 (.A0(n242), .A1(n239), .B0(n257), .Y(n3));
    AOI22X1  U27 (.A0(rec_dataH_rec[6]), .A1(n8), .B0(rec_dataH_rec[5]), .B1(
        n18), .Y(n23));
    AOI22X1  U29 (.A0(rec_dataH_rec[7]), .A1(n8), .B0(rec_dataH_rec[6]), .B1(
        n18), .Y(n24));
    AOI22X1  U31 (.A0(iRECEIVER_rec_datH), .A1(n8), .B0(rec_dataH_rec[7]), .B1(
        n18), .Y(n25));
    AOI22X1  U33 (.A0(xmit_dataH[0]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_1_)
        , .B1(n29), .Y(n27));
    AOI22X1  U36 (.A0(xmit_dataH[1]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_2_)
        , .B1(n29), .Y(n31));
    AOI22X1  U39 (.A0(xmit_dataH[2]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_3_)
        , .B1(n29), .Y(n33));
    AOI22X1  U42 (.A0(xmit_dataH[3]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_4_)
        , .B1(n29), .Y(n35));
    AOI22X1  U45 (.A0(xmit_dataH[4]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_5_)
        , .B1(n29), .Y(n37));
    AOI22X1  U48 (.A0(xmit_dataH[5]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_6_)
        , .B1(n29), .Y(n39));
    AOI22X1  U51 (.A0(xmit_dataH[6]), .A1(n28), .B0(iXMIT_xmit_ShiftRegH_7_)
        , .B1(n29), .Y(n41));
    AOI22X1  U59 (.A0(n46), .A1(iXMIT_bitCountH_3_), .B0(iXMIT_N46), .B1(n47)
        , .Y(n45));
    AOI22X1  U61 (.A0(iXMIT_bitCountH_2_), .A1(n46), .B0(iXMIT_N45), .B1(n47)
        , .Y(n48));
    AOI22X1  U63 (.A0(iXMIT_bitCountH_1_), .A1(n46), .B0(iXMIT_N44), .B1(n47)
        , .Y(n49));
    AOI22X1  U65 (.A0(iXMIT_bitCountH_0_), .A1(n46), .B0(n252), .B1(n47), .Y(
        n50));
    AOI22X1  U75 (.A0(n54), .A1(n61), .B0(n62), .B1(iXMIT_state_0_), .Y(n60));
    AOI22X1  U83 (.A0(n54), .A1(n53), .B0(iXMIT_state_2_), .B1(n239), .Y(n67));
    AOI22X1  U92 (.A0(n66), .A1(n74), .B0(n54), .B1(n65), .Y(n73));
    AOI22X1  U117 (.A0(n88), .A1(iRECEIVER_state_1_), .B0(iRECEIVER_rec_datH)
        , .B1(n241), .Y(n87));
    AOI22X1  U7 (.A0(iRECEIVER_N27), .A1(n8), .B0(iRECEIVER_recd_bitCntrH_2_)
        , .B1(n9), .Y(n7));
    AOI22X1  U9 (.A0(iRECEIVER_N26), .A1(n8), .B0(iRECEIVER_recd_bitCntrH_1_)
        , .B1(n9), .Y(n10));
    AOI22X1  U11 (.A0(n243), .A1(n8), .B0(iRECEIVER_recd_bitCntrH_0_), .B1(n9)
        , .Y(n11));
    AOI22X1  U13 (.A0(iRECEIVER_N28), .A1(n8), .B0(iRECEIVER_recd_bitCntrH_3_)
        , .B1(n9), .Y(n12));
    AOI22X1  U17 (.A0(rec_dataH_rec[1]), .A1(n8), .B0(rec_dataH_rec[0]), .B1(
        n18), .Y(n17));
    AOI22X1  U19 (.A0(rec_dataH_rec[2]), .A1(n8), .B0(rec_dataH_rec[1]), .B1(
        n18), .Y(n19));
    AOI22X1  U21 (.A0(rec_dataH_rec[3]), .A1(n8), .B0(rec_dataH_rec[2]), .B1(
        n18), .Y(n20));
    AOI22X1  U23 (.A0(rec_dataH_rec[4]), .A1(n8), .B0(rec_dataH_rec[3]), .B1(
        n18), .Y(n21));
    AOI22X1  U25 (.A0(rec_dataH_rec[5]), .A1(n8), .B0(rec_dataH_rec[4]), .B1(
        n18), .Y(n22));
    OR2X1  U302 (.A(iXMIT_CRTL), .B(iRECEIVER_state_CTRL), .Y(iCTRL));
    OR2X1  U113 (.A(iRECEIVER_state_0_), .B(n84), .Y(n81));
    OR4X1  U296 (.A(iXMIT_state_CTRL), .B(iXMIT_N_CTRL_1_), .C(iXMIT_N_CTRL_2_)
        , .D(iXMIT_xmit_CTRL), .Y(iXMIT_CRTL));
    OR4X1  U85 (.A(n253), .B(iXMIT_bitCountH_0_), .C(iXMIT_bitCountH_1_), .D(
        iXMIT_bitCountH_2_), .Y(n69));
    NAND2X1  U207 (.A(n63), .B(n44), .Y(iXMIT_next_state_1_));
    NAND2X1  U208 (.A(iXMIT_bitCountH_1_), .B(iXMIT_bitCountH_0_), .Y(n270));
    NAND2X1  U209 (.A(n61), .B(n69), .Y(n53));
    NAND2X1  U210 (.A(iRECEIVER_recd_bitCntrH_1_), .B(
        iRECEIVER_recd_bitCntrH_0_), .Y(n274));
    NAND2X1  U211 (.A(iXMIT_bitCell_cntrH_1_), .B(iXMIT_bitCell_cntrH_0_), .Y(
        n268));
    NAND2X1  U212 (.A(iRECEIVER_bitCell_cntrH_1_), .B(
        iRECEIVER_bitCell_cntrH_0_), .Y(n272));
    NAND2X1  U213 (.A(n55), .B(n56), .Y(iXMIT_xmit_doneInH));
    NAND2X1  U289 (.A(1'b1), .B(\test_point/TM ), .Y(n370));
    NAND2X1  U201 (.A(n80), .B(n91), .Y(n83));
    NAND2X1  U204 (.A(n67), .B(n68), .Y(iXMIT_next_state_0_));
    NAND2X1  U205 (.A(n42), .B(n43), .Y(n211));
    NAND2X1  U206 (.A(xmit_dataH[7]), .B(n26), .Y(n43));
    NAND3X1  U71 (.A(iXMIT_state_2_), .B(iXMIT_state_0_), .C(n57), .Y(n56));
    NAND3X1  U72 (.A(n242), .B(n58), .C(n246), .Y(n55));
    NAND3X1  U79 (.A(n246), .B(n242), .C(xmitH), .Y(n64));
    NAND3X1  U102 (.A(iXMIT_bitCell_cntrH_2_), .B(iXMIT_bitCell_cntrH_1_), .C(
        iXMIT_bitCell_cntrH_3_), .Y(n75));
    NAND3X1  U107 (.A(n241), .B(n238), .C(iRECEIVER_rec_datH), .Y(n77));
    NAND3X1  U112 (.A(n241), .B(n238), .C(n248), .Y(n82));
    SDFFSRX1  iXMIT_bitCell_cntrH_reg_2_ (.CK(sys_clk), .D(iXMIT_N28), .Q(
        iXMIT_bitCell_cntrH_2_), .QN(n251), .RN(n266), .SE(test_se), .SI(
        iXMIT_bitCell_cntrH_1_), .SN(1'b1));
    SDFFSRX1  iXMIT_state_reg_0_ (.CK(sys_clk), .D(iXMIT_next_state_0_), .Q(
        iXMIT_state_0_), .QN(n239), .RN(sys_rst_l), .SE(test_se), .SI(
        iXMIT_bitCountH_3_), .SN(1'b1));
    SDFFSRX1  iXMIT_state_reg_2_ (.CK(sys_clk), .D(iXMIT_next_state_2_), .Q(
        iXMIT_state_2_), .QN(n242), .RN(sys_rst_l), .SE(test_se), .SI(
        iXMIT_state_1_), .SN(1'b1));
    SDFFSRX1  iXMIT_state_reg_1_ (.CK(sys_clk), .D(iXMIT_next_state_1_), .Q(
        iXMIT_state_1_), .QN(n246), .RN(sys_rst_l), .SE(test_se), .SI(
        iXMIT_state_0_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCountH_reg_0_ (.CK(sys_clk), .D(n223), .Q(
        iXMIT_bitCountH_0_), .QN(n252), .RN(n266), .SE(test_se), .SI(
        iXMIT_bitCell_cntrH_3_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCountH_reg_1_ (.CK(sys_clk), .D(n220), .Q(
        iXMIT_bitCountH_1_), .RN(n265), .SE(test_se), .SI(iXMIT_bitCountH_0_)
        , .SN(1'b1));
    SDFFSRX1  iXMIT_bitCountH_reg_2_ (.CK(sys_clk), .D(n217), .Q(
        iXMIT_bitCountH_2_), .QN(n247), .RN(n264), .SE(test_se), .SI(
        iXMIT_bitCountH_1_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCountH_reg_3_ (.CK(sys_clk), .D(n214), .Q(
        iXMIT_bitCountH_3_), .QN(n253), .RN(n266), .SE(test_se), .SI(
        iXMIT_bitCountH_2_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_7_ (.CK(sys_clk), .D(n211), .Q(
        iXMIT_xmit_ShiftRegH_7_), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_6_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_6_ (.CK(sys_clk), .D(n208), .Q(
        iXMIT_xmit_ShiftRegH_6_), .QN(n258), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_5_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_5_ (.CK(sys_clk), .D(n205), .Q(
        iXMIT_xmit_ShiftRegH_5_), .QN(n259), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_4_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_4_ (.CK(sys_clk), .D(n202), .Q(
        iXMIT_xmit_ShiftRegH_4_), .QN(n260), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_3_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_3_ (.CK(sys_clk), .D(n199), .Q(
        iXMIT_xmit_ShiftRegH_3_), .QN(n261), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_2_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_2_ (.CK(sys_clk), .D(n196), .Q(
        iXMIT_xmit_ShiftRegH_2_), .QN(n262), .RN(n266), .SE(test_se), .SI(
        iXMIT_xmit_ShiftRegH_1_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_1_ (.CK(sys_clk), .D(n193), .Q(
        iXMIT_xmit_ShiftRegH_1_), .QN(n263), .RN(n266), .SE(test_se), .SI(n281)
        , .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_doneH_reg (.CK(sys_clk), .D(iXMIT_xmit_doneInH), .Q(
        xmit_doneH_temp), .RN(n266), .SE(test_se), .SI(iXMIT_xmit_ShiftRegH_7_)
        , .SN(1'b1));
    SDFFSRX1  iRECEIVER_state_reg_1_ (.CK(sys_clk), .D(iRECEIVER_next_state_1_)
        , .Q(iRECEIVER_state_1_), .QN(n241), .RN(n265), .SE(test_se), .SI(
        iRECEIVER_state_0_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_state_reg_0_ (.CK(sys_clk), .D(iRECEIVER_next_state_0_)
        , .Q(iRECEIVER_state_0_), .QN(n245), .RN(1'b1), .SE(test_se), .SI(
        iRECEIVER_recd_bitCntrH_3_), .SN(n265));
    SDFFSRX1  iRECEIVER_bitCell_cntrH_reg_0_ (.CK(sys_clk), .D(iRECEIVER_N20)
        , .Q(iRECEIVER_bitCell_cntrH_0_), .QN(n255), .RN(n265), .SE(test_se)
        , .SI(test_si), .SN(1'b1));
    SDFFSRX1  iRECEIVER_bitCell_cntrH_reg_1_ (.CK(sys_clk), .D(iRECEIVER_N21)
        , .Q(iRECEIVER_bitCell_cntrH_1_), .QN(n244), .RN(n265), .SE(test_se)
        , .SI(iRECEIVER_bitCell_cntrH_0_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_bitCell_cntrH_reg_2_ (.CK(sys_clk), .D(iRECEIVER_N22)
        , .Q(iRECEIVER_bitCell_cntrH_2_), .QN(n249), .RN(n265), .SE(test_se)
        , .SI(iRECEIVER_bitCell_cntrH_1_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_bitCell_cntrH_reg_3_ (.CK(sys_clk), .D(iRECEIVER_N23)
        , .Q(iRECEIVER_bitCell_cntrH_3_), .QN(n256), .RN(n265), .SE(test_se)
        , .SI(iRECEIVER_bitCell_cntrH_2_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_state_reg_2_ (.CK(sys_clk), .D(iRECEIVER_next_state_2_)
        , .Q(iRECEIVER_state_2_), .QN(n238), .RN(n265), .SE(test_se), .SI(
        iRECEIVER_state_1_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_rec_readyH_reg (.CK(sys_clk), .D(
        iRECEIVER_rec_readyInH), .Q(rec_readyH), .RN(n265), .SE(test_se), .SI(
        iRECEIVER_rec_datSyncH), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_7_ (.CK(sys_clk), .D(n165), .Q(
        rec_dataH_rec[7]), .RN(n265), .SE(test_se), .SI(rec_dataH_rec[6]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_7_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[7]), .Q(rec_dataH_temp[7]), .RN(n265), .SE(test_se), .SI(
        rec_dataH_temp[6]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_7_ (.CK(sys_clk), .D(rec_dataH_temp[7]), .Q(
        rec_dataH[7]), .RN(n265), .SE(test_se), .SI(rec_dataH[6]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_6_ (.CK(sys_clk), .D(n158), .Q(
        rec_dataH_rec[6]), .RN(n265), .SE(test_se), .SI(rec_dataH_rec[5]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_6_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[6]), .Q(rec_dataH_temp[6]), .RN(n265), .SE(test_se), .SI(
        rec_dataH_temp[5]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_6_ (.CK(sys_clk), .D(rec_dataH_temp[6]), .Q(
        rec_dataH[6]), .RN(n264), .SE(test_se), .SI(rec_dataH[5]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_5_ (.CK(sys_clk), .D(n151), .Q(
        rec_dataH_rec[5]), .RN(n266), .SE(test_se), .SI(rec_dataH_rec[4]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_5_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[5]), .Q(rec_dataH_temp[5]), .RN(n266), .SE(test_se), .SI(
        rec_dataH_temp[4]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_5_ (.CK(sys_clk), .D(rec_dataH_temp[5]), .Q(
        rec_dataH[5]), .RN(n265), .SE(test_se), .SI(rec_dataH[4]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_4_ (.CK(sys_clk), .D(n144), .Q(
        rec_dataH_rec[4]), .RN(n266), .SE(test_se), .SI(rec_dataH_rec[3]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_4_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[4]), .Q(rec_dataH_temp[4]), .RN(n264), .SE(test_se), .SI(
        rec_dataH_temp[3]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_4_ (.CK(sys_clk), .D(rec_dataH_temp[4]), .Q(
        rec_dataH[4]), .RN(n266), .SE(test_se), .SI(rec_dataH[3]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_3_ (.CK(sys_clk), .D(n137), .Q(
        rec_dataH_rec[3]), .RN(n265), .SE(test_se), .SI(rec_dataH_rec[2]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_3_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[3]), .Q(rec_dataH_temp[3]), .RN(n264), .SE(test_se), .SI(
        rec_dataH_temp[2]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_3_ (.CK(sys_clk), .D(rec_dataH_temp[3]), .Q(
        rec_dataH[3]), .RN(n265), .SE(test_se), .SI(rec_dataH[2]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_2_ (.CK(sys_clk), .D(n130), .Q(
        rec_dataH_rec[2]), .RN(n264), .SE(test_se), .SI(rec_dataH_rec[1]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_2_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[2]), .Q(rec_dataH_temp[2]), .RN(n264), .SE(test_se), .SI(
        rec_dataH_temp[1]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_2_ (.CK(sys_clk), .D(rec_dataH_temp[2]), .Q(
        rec_dataH[2]), .RN(n264), .SE(test_se), .SI(rec_dataH[1]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_1_ (.CK(sys_clk), .D(n123), .Q(
        rec_dataH_rec[1]), .RN(n264), .SE(test_se), .SI(rec_dataH_rec[0]), .SN(
        1'b1));
    SDFFSRX1  rec_dataH_temp_reg_1_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[1]), .Q(rec_dataH_temp[1]), .RN(n264), .SE(test_se), .SI(
        rec_dataH_temp[0]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_1_ (.CK(sys_clk), .D(rec_dataH_temp[1]), .Q(
        rec_dataH[1]), .RN(n264), .SE(test_se), .SI(rec_dataH[0]), .SN(1'b1));
    SDFFSRX1  iRECEIVER_par_dataH_reg_0_ (.CK(sys_clk), .D(n116), .Q(
        rec_dataH_rec[0]), .RN(n264), .SE(test_se), .SI(
        iRECEIVER_bitCell_cntrH_3_), .SN(1'b1));
    SDFFSRX1  rec_dataH_temp_reg_0_ (.CK(\test_point/DOUT ), .D(
        rec_dataH_rec[0]), .Q(rec_dataH_temp[0]), .RN(n264), .SE(test_se), .SI(
        rec_dataH[7]), .SN(1'b1));
    SDFFSRX1  rec_dataH_reg_0_ (.CK(sys_clk), .D(rec_dataH_temp[0]), .Q(
        rec_dataH[0]), .RN(n264), .SE(test_se), .SI(xmit_doneH_temp), .SN(1'b1)
        );
    SDFFSRX1  iRECEIVER_recd_bitCntrH_reg_3_ (.CK(sys_clk), .D(n109), .Q(
        iRECEIVER_recd_bitCntrH_3_), .RN(n264), .SE(test_se), .SI(
        iRECEIVER_recd_bitCntrH_2_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_recd_bitCntrH_reg_0_ (.CK(sys_clk), .D(n106), .Q(
        iRECEIVER_recd_bitCntrH_0_), .QN(n243), .RN(n264), .SE(test_se), .SI(
        rec_readyH), .SN(1'b1));
    SDFFSRX1  iRECEIVER_recd_bitCntrH_reg_1_ (.CK(sys_clk), .D(n103), .Q(
        iRECEIVER_recd_bitCntrH_1_), .RN(n264), .SE(test_se), .SI(
        iRECEIVER_recd_bitCntrH_0_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_recd_bitCntrH_reg_2_ (.CK(sys_clk), .D(n100), .Q(
        iRECEIVER_recd_bitCntrH_2_), .QN(n250), .RN(n264), .SE(test_se), .SI(
        iRECEIVER_recd_bitCntrH_1_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCell_cntrH_reg_3_ (.CK(sys_clk), .D(iXMIT_N29), .Q(
        iXMIT_bitCell_cntrH_3_), .RN(n265), .SE(test_se), .SI(
        iXMIT_bitCell_cntrH_2_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCell_cntrH_reg_0_ (.CK(sys_clk), .D(iXMIT_N26), .Q(
        iXMIT_bitCell_cntrH_0_), .QN(n254), .RN(sys_rst_l), .SE(test_se), .SI(
        iRECEIVER_state_2_), .SN(1'b1));
    SDFFSRX1  iXMIT_bitCell_cntrH_reg_1_ (.CK(sys_clk), .D(iXMIT_N27), .Q(
        iXMIT_bitCell_cntrH_1_), .RN(n264), .SE(test_se), .SI(
        iXMIT_bitCell_cntrH_0_), .SN(1'b1));
    SDFFSRX1  iXMIT_xmit_ShiftRegH_reg_0_ (.CK(sys_clk), .D(n190), .Q(n281)
        , .QN(n257), .RN(n266), .SE(test_se), .SI(iXMIT_state_2_), .SN(1'b1));
    SDFFSRX1  iRECEIVER_rec_datSyncH_reg (.CK(sys_clk), .D(uart_REC_dataH), .Q(
        iRECEIVER_rec_datSyncH), .RN(1'b1), .SE(test_se), .SI(
        iRECEIVER_rec_datH), .SN(n266));
    SDFFSRX1  iRECEIVER_rec_datH_reg (.CK(sys_clk), .D(iRECEIVER_rec_datSyncH)
        , .Q(iRECEIVER_rec_datH), .QN(n248), .RN(1'b1), .SE(test_se), .SI(
        rec_dataH_rec[7]), .SN(n266));
    NAND4X1  U292 (.A(ena), .B(iXMIT_state_0_), .C(iXMIT_state_1_), .D(
        iXMIT_state_2_), .Y(iXMIT_state_CTRL));
    NAND4X1  U293 (.A(ena), .B(iXMIT_N45), .C(iXMIT_N44), .D(iXMIT_N29), .Y(
        iXMIT_N_CTRL_1_));
    NAND4X1  U294 (.A(ena), .B(iXMIT_N27), .C(iXMIT_N26), .D(iXMIT_N25), .Y(
        iXMIT_N_CTRL_2_));
    NAND4X1  U295 (.A(ena), .B(iXMIT_xmit_ShiftRegH_7_), .C(
        iXMIT_xmit_ShiftRegH_6_), .D(iXMIT_xmit_ShiftRegH_5_), .Y(
        iXMIT_xmit_CTRL));
    NAND4X1  U297 (.A(ena), .B(iRECEIVER_state_0_), .C(iRECEIVER_state_1_), .D(
        iRECEIVER_state_2_), .Y(iRECEIVER_state_CTRL));
    NAND4X1  U109 (.A(n81), .B(n82), .C(n18), .D(n83), .Y(
        iRECEIVER_next_state_1_));
    NAND4X1  U116 (.A(n83), .B(n238), .C(n86), .D(n87), .Y(
        iRECEIVER_next_state_0_));
    NAND4X1  U118 (.A(n80), .B(iRECEIVER_recd_bitCntrH_3_), .C(n89), .D(n243)
        , .Y(n86));
    NAND4X1  U132 (.A(iRECEIVER_bitCell_cntrH_2_), .B(n255), .C(n244), .D(n256)
        , .Y(n85));
    NAND4X1  U138 (.A(iRECEIVER_bitCell_cntrH_3_), .B(
        iRECEIVER_bitCell_cntrH_2_), .C(iRECEIVER_bitCell_cntrH_1_), .D(n255)
        , .Y(n91));
    MX2X1  U291 (.A(rec_readyH), .B(sys_clk), .S0(n371), .Y(\test_point/DOUT )
        );
    INVX1  U214 (.A(n64), .Y(n28));
    INVX1  U290 (.A(n370), .Y(n371));
    INVX1  U28 (.A(n24), .Y(n158));
    INVX1  U30 (.A(n25), .Y(n165));
    INVX1  U55 (.A(n44), .Y(n26));
    INVX1  U58 (.A(n45), .Y(n214));
    INVX1  U60 (.A(n48), .Y(n217));
    INVX1  U62 (.A(n49), .Y(n220));
    INVX1  U64 (.A(n50), .Y(n223));
    INVX1  U68 (.A(n54), .Y(n52));
    INVX1  U69 (.A(n55), .Y(n51));
    INVX1  U73 (.A(xmitH), .Y(n58));
    INVX1  U74 (.A(n60), .Y(iXMIT_next_state_2_));
    INVX1  U93 (.A(n61), .Y(n65));
    INVX1  U96 (.A(n57), .Y(n74));
    INVX1  U99 (.A(n62), .Y(n72));
    INVX1  U131 (.A(n85), .Y(n88));
    INVX1  U137 (.A(n91), .Y(n79));
    INVX1  U198 (.A(n267), .Y(n265));
    INVX1  U199 (.A(n267), .Y(n266));
    INVX1  U200 (.A(n267), .Y(n264));
    INVX1  U202 (.A(n8), .Y(n18));
    INVX1  U203 (.A(sys_rst_l), .Y(n267));
    INVX1  U6 (.A(n7), .Y(n100));
    INVX1  U8 (.A(n10), .Y(n103));
    INVX1  U10 (.A(n11), .Y(n106));
    INVX1  U12 (.A(n12), .Y(n109));
    INVX1  U16 (.A(n17), .Y(n116));
    INVX1  U18 (.A(n19), .Y(n123));
    INVX1  U20 (.A(n20), .Y(n130));
    INVX1  U22 (.A(n21), .Y(n137));
    INVX1  U24 (.A(n22), .Y(n144));
    INVX1  U26 (.A(n23), .Y(n151));
    AND2X1  U303 (.A(iCTRL), .B(xmit_doneH_temp), .Y(xmit_doneH));
    AND2X1  U87 (.A(iXMIT_N25), .B(n71), .Y(iXMIT_N29));
    AND2X1  U88 (.A(iXMIT_N24), .B(n71), .Y(iXMIT_N28));
    AND2X1  U89 (.A(iXMIT_N23), .B(n71), .Y(iXMIT_N27));
    AND2X1  U90 (.A(n254), .B(n71), .Y(iXMIT_N26));
    AND2X1  U108 (.A(n79), .B(n80), .Y(iRECEIVER_next_state_2_));
    AND2X1  U124 (.A(iRECEIVER_N19), .B(n92), .Y(iRECEIVER_N23));
    AND2X1  U125 (.A(iRECEIVER_N18), .B(n92), .Y(iRECEIVER_N22));
    AND2X1  U126 (.A(iRECEIVER_N17), .B(n92), .Y(iRECEIVER_N21));
    AND2X1  U127 (.A(n255), .B(n92), .Y(iRECEIVER_N20));
    AND2X1  U128 (.A(n93), .B(n94), .Y(n92));
    XOR2X1  U215 (.A(iXMIT_bitCell_cntrH_1_), .B(iXMIT_bitCell_cntrH_0_), .Y(
        iXMIT_N23));
    XOR2X1  U216 (.A(n251), .B(n268), .Y(iXMIT_N24));
    XOR2X1  U218 (.A(iXMIT_bitCell_cntrH_3_), .B(n269), .Y(iXMIT_N25));
    XOR2X1  U219 (.A(iXMIT_bitCountH_1_), .B(iXMIT_bitCountH_0_), .Y(iXMIT_N44)
        );
    XOR2X1  U220 (.A(n247), .B(n270), .Y(iXMIT_N45));
    XOR2X1  U222 (.A(iXMIT_bitCountH_3_), .B(n271), .Y(iXMIT_N46));
    XOR2X1  U223 (.A(iRECEIVER_bitCell_cntrH_1_), .B(
        iRECEIVER_bitCell_cntrH_0_), .Y(iRECEIVER_N17));
    XOR2X1  U224 (.A(n249), .B(n272), .Y(iRECEIVER_N18));
    XOR2X1  U226 (.A(iRECEIVER_bitCell_cntrH_3_), .B(n273), .Y(iRECEIVER_N19));
    XOR2X1  U227 (.A(iRECEIVER_recd_bitCntrH_1_), .B(
        iRECEIVER_recd_bitCntrH_0_), .Y(iRECEIVER_N26));
    XOR2X1  U228 (.A(n250), .B(n274), .Y(iRECEIVER_N27));
    XOR2X1  U230 (.A(iRECEIVER_recd_bitCntrH_3_), .B(n275), .Y(iRECEIVER_N28));
endmodule
