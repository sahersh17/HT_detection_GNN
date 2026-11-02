library ieee;
use ieee.std_logic_1164.all;
entity shift_equivalence is end;
architecture test of shift_equivalence is
begin
  process
    variable a, b, c : bit_vector(7 downto 0);
    variable n : integer;
  begin
    for n in 0 to 255 loop
      for i in 0 to 7 loop
        if ((n / (2 ** i)) mod 2) = 1 then a(i) := '1'; else a(i) := '0'; end if;
      end loop;
      b := a sla 1;
      c := a(6 downto 0) & a(0);
      assert b = c report "shift mismatch" severity failure;
    end loop;
    report "256 shift inputs agree" severity note;
    wait;
  end process;
end;
