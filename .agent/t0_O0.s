	.file	"t0.c"
	.text
	.globl	abc
	.def	abc;	.scl	2;	.type	32;	.endef
	.seh_proc	abc
abc:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	cmpl	$0, 16(%rbp)
	jle	.L4
	movl	16(%rbp), %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	abc
	jmp	.L1
.L4:
	nop
.L1:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
