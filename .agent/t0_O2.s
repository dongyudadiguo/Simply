	.file	"t0.c"
	.text
	.p2align 4
	.globl	abc
	.def	abc;	.scl	2;	.type	32;	.endef
	.seh_proc	abc
abc:
	.seh_endprologue
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
