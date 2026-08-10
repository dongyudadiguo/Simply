	.file	"compare_tramp.c"
	.text
	.p2align 4
	.globl	step2
	.def	step2;	.scl	2;	.type	32;	.endef
	.seh_proc	step2
step2:
	.seh_endprologue
	movl	$1, %r8d
	movq	(%rdx), %xmm0
	movq	%rcx, %rax
	movq	%rdx, %rcx
	movd	%xmm0, %edx
	cmpl	$1, %edx
	jle	.L2
	pshufd	$0xe5, %xmm0, %xmm1
	movl	8(%rcx), %r8d
	movd	%xmm1, %ecx
	imull	%edx, %ecx
	leal	-1(%rdx), %r9d
	movd	%r9d, %xmm0
	movd	%ecx, %xmm2
	punpckldq	%xmm2, %xmm0
.L2:
	movq	%xmm0, (%rax)
	movl	%r8d, 8(%rax)
	ret
	.seh_endproc
	.p2align 4
	.globl	factorial3
	.def	factorial3;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial3
factorial3:
	.seh_endprologue
	movl	$1, %edx
	cmpl	$1, %ecx
	movl	%ecx, %eax
	jle	.L5
	testb	$1, %cl
	jne	.L8
	subl	$1, %eax
	movl	%ecx, %edx
	cmpl	$1, %eax
	je	.L5
.L8:
	imull	%eax, %edx
	leal	-1(%rax), %ecx
	subl	$2, %eax
	imull	%ecx, %edx
	cmpl	$1, %eax
	jne	.L8
.L5:
	movl	%edx, %eax
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
