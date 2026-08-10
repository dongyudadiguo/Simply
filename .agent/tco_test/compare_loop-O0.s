	.file	"compare_loop.c"
	.text
	.globl	step
	.def	step;	.scl	2;	.type	32;	.endef
	.seh_proc	step
step:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	%edx, 24(%rbp)
	cmpl	$1, 16(%rbp)
	jg	.L2
	movl	24(%rbp), %eax
	jmp	.L3
.L2:
	movl	24(%rbp), %eax
	imull	16(%rbp), %eax
.L3:
	popq	%rbp
	ret
	.seh_endproc
	.globl	factorial2
	.def	factorial2;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial2
factorial2:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$16, %rsp
	.seh_stackalloc	16
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	$1, -4(%rbp)
.L7:
	cmpl	$1, 16(%rbp)
	jg	.L5
	movl	-4(%rbp), %eax
	jmp	.L8
.L5:
	movl	-4(%rbp), %eax
	imull	16(%rbp), %eax
	movl	%eax, -4(%rbp)
	subl	$1, 16(%rbp)
	jmp	.L7
.L8:
	addq	$16, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
