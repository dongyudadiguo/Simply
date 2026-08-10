	.file	"mutual.c"
	.text
	.globl	is_even
	.def	is_even;	.scl	2;	.type	32;	.endef
	.seh_proc	is_even
is_even:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	cmpl	$0, 16(%rbp)
	jne	.L2
	movl	$1, %eax
	jmp	.L3
.L2:
	movl	16(%rbp), %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	is_odd
.L3:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	is_odd
	.def	is_odd;	.scl	2;	.type	32;	.endef
	.seh_proc	is_odd
is_odd:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	cmpl	$0, 16(%rbp)
	jne	.L5
	movl	$0, %eax
	jmp	.L6
.L5:
	movl	16(%rbp), %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	is_even
.L6:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
