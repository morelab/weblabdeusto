library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;

entity base is
	Port (
	
		A: in std_logic;
		B: in std_logic;
		S0: out std_logic;
		S1: out std_logic;
		
		Clk : in std_logic;
	
		Leds : inout std_logic_vector (7 downto 0);
		Enable_seg_out : inout std_logic_vector (3 downto 0);
		Seven_seg : inout std_logic_vector (6 downto 0);
		Punto: inout std_logic;
	
		Buttons: in std_logic_vector (3 downto 0);
		Switches: in std_logic_vector (9 downto 0)
		);
end base;

architecture behavioral of base is
begin
	S0<=((A and not(B)) or (not(A) and B));
	S1<=((not(A) and not(B)) or (A and B));
	
	Leds <= Switches(7 downto 0);
end behavioral;
