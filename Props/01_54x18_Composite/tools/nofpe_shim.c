/* The Ubuntu XFOIL build enables floating-point exception traps (gfortran -ffpe-trap), which makes it abort with
   SIGFPE when graphics are disabled (PLOP G F). Upstream XFOIL runs with traps off. This preload shim turns the
   request to enable traps into a no-op, restoring the default IEEE behaviour. It changes nothing else. */
void _gfortran_set_fpe(int exceptions) { (void)exceptions; }
