	.file	"t4.c"
	.text
	.p2align 4
	.globl	dispatch
	.def	dispatch;	.scl	2;	.type	32;	.endef
	.seh_proc	dispatch
dispatch:
	.seh_endprologue
	testl	%edx, %edx
	movq	%rcx, %rax
	jle	.L1
	leal	-1(%rdx), %ecx
	rex.W jmp	*%rax
	.p2align 4,,10
	.p2align 3
.L1:
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
