	.file	"bench.c"
	.text
	.def	mix;	.scl	3;	.type	32;	.endef
	.seh_proc	mix
mix:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	16(%rbp), %eax
	sall	$13, %eax
	xorl	%eax, 16(%rbp)
	movl	16(%rbp), %eax
	shrl	$17, %eax
	xorl	%eax, 16(%rbp)
	movl	16(%rbp), %eax
	sall	$5, %eax
	xorl	%eax, 16(%rbp)
	movl	16(%rbp), %eax
	popq	%rbp
	ret
	.seh_endproc
	.globl	loop_iter
	.def	loop_iter;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_iter
loop_iter:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$48, %rsp
	.seh_stackalloc	48
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	$0, -4(%rbp)
	jmp	.L4
.L5:
	subl	$1, 16(%rbp)
	movl	-4(%rbp), %edx
	movl	16(%rbp), %eax
	addl	%edx, %eax
	movl	%eax, %ecx
	call	mix
	movl	%eax, -4(%rbp)
.L4:
	cmpl	$0, 16(%rbp)
	jne	.L5
	movl	-4(%rbp), %eax
	addq	$48, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	loop_tail
	.def	loop_tail;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tail
loop_tail:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	%edx, 24(%rbp)
	cmpl	$0, 16(%rbp)
	jne	.L8
	movl	24(%rbp), %eax
	jmp	.L9
.L8:
	movl	16(%rbp), %edx
	movl	24(%rbp), %eax
	addl	%edx, %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	mix
	movl	%eax, %edx
	movl	16(%rbp), %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	loop_tail
.L9:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	tail_wrap
	.def	tail_wrap;	.scl	2;	.type	32;	.endef
	.seh_proc	tail_wrap
tail_wrap:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	16(%rbp), %eax
	movl	$0, %edx
	movl	%eax, %ecx
	call	loop_tail
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	loop_tramp_sep
	.def	loop_tramp_sep;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tramp_sep
loop_tramp_sep:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$48, %rsp
	.seh_stackalloc	48
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	$0, -4(%rbp)
.L15:
	cmpl	$0, 16(%rbp)
	jne	.L13
	movl	-4(%rbp), %eax
	jmp	.L16
.L13:
	movl	16(%rbp), %eax
	subl	$1, %eax
	movl	-4(%rbp), %edx
	movl	%eax, %ecx
	call	imp
	movl	%eax, -4(%rbp)
	subl	$1, 16(%rbp)
	jmp	.L15
.L16:
	addq	$48, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	loop_tramp_inl
	.def	loop_tramp_inl;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tramp_inl
loop_tramp_inl:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$48, %rsp
	.seh_stackalloc	48
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	$0, -4(%rbp)
.L20:
	cmpl	$0, 16(%rbp)
	jne	.L18
	movl	-4(%rbp), %eax
	jmp	.L21
.L18:
	movl	16(%rbp), %edx
	movl	-4(%rbp), %eax
	addl	%edx, %eax
	subl	$1, %eax
	movl	%eax, %ecx
	call	mix
	movl	%eax, -4(%rbp)
	subl	$1, 16(%rbp)
	jmp	.L20
.L21:
	addq	$48, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.globl	bench
	.def	bench;	.scl	2;	.type	32;	.endef
	.seh_proc	bench
bench:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$48, %rsp
	.seh_stackalloc	48
	.seh_endprologue
	movq	%rcx, 16(%rbp)
	movl	%edx, 24(%rbp)
	movl	%r8d, 32(%rbp)
	call	clock
	movl	%eax, -8(%rbp)
	movl	$0, -16(%rbp)
	movl	$0, -4(%rbp)
	jmp	.L23
.L24:
	movl	24(%rbp), %eax
	movq	16(%rbp), %rdx
	movl	%eax, %ecx
	call	*%rdx
	movl	-16(%rbp), %edx
	addl	%edx, %eax
	movl	%eax, -16(%rbp)
	addl	$1, -4(%rbp)
.L23:
	movl	-4(%rbp), %eax
	cmpl	32(%rbp), %eax
	jl	.L24
	call	clock
	movl	%eax, -12(%rbp)
	movl	-12(%rbp), %eax
	subl	-8(%rbp), %eax
	pxor	%xmm0, %xmm0
	cvtsi2sdl	%eax, %xmm0
	movsd	.LC0(%rip), %xmm1
	divsd	%xmm1, %xmm0
	addq	$48, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.section .rdata,"dr"
.LC1:
	.ascii "\242\331 \264\277\265\374\264\372(\273\371\327\274)     \0"
.LC2:
	.ascii "\242\332 \316\262\265\335\271\351(TCO)      \0"
.LC3:
	.ascii "\242\333 \261\304\264\262-\315\342\262\277imp(\262\273\304\332\301\252)\0"
.LC4:
	.ascii "\242\334 \261\304\264\262-\304\332\301\252imp     \0"
.LC5:
	.ascii "%s : %7.3f ms\12\0"
	.text
	.globl	main
	.def	main;	.scl	2;	.type	32;	.endef
	.seh_proc	main
main:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$112, %rsp
	.seh_stackalloc	112
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movq	%rdx, 24(%rbp)
	call	__main
	movq	24(%rbp), %rax
	addq	$8, %rax
	movq	(%rax), %rax
	movq	%rax, %rcx
	call	atoi
	movl	%eax, -8(%rbp)
	movq	24(%rbp), %rax
	addq	$16, %rax
	movq	(%rax), %rax
	movq	%rax, %rcx
	call	atoi
	movl	%eax, -12(%rbp)
	leaq	.LC1(%rip), %rax
	movq	%rax, -80(%rbp)
	leaq	loop_iter(%rip), %rax
	movq	%rax, -72(%rbp)
	leaq	.LC2(%rip), %rax
	movq	%rax, -64(%rbp)
	leaq	tail_wrap(%rip), %rax
	movq	%rax, -56(%rbp)
	leaq	.LC3(%rip), %rax
	movq	%rax, -48(%rbp)
	leaq	loop_tramp_sep(%rip), %rax
	movq	%rax, -40(%rbp)
	leaq	.LC4(%rip), %rax
	movq	%rax, -32(%rbp)
	leaq	loop_tramp_inl(%rip), %rax
	movq	%rax, -24(%rbp)
	movl	$4, -16(%rbp)
	movl	$0, -4(%rbp)
	jmp	.L27
.L28:
	movl	-4(%rbp), %eax
	cltq
	salq	$4, %rax
	addq	%rbp, %rax
	subq	$72, %rax
	movq	(%rax), %rax
	movl	-12(%rbp), %ecx
	movl	-8(%rbp), %edx
	movl	%ecx, %r8d
	movq	%rax, %rcx
	call	bench
	movsd	.LC0(%rip), %xmm1
	mulsd	%xmm1, %xmm0
	movl	-4(%rbp), %eax
	cltq
	salq	$4, %rax
	addq	%rbp, %rax
	subq	$80, %rax
	movq	(%rax), %rdx
	movapd	%xmm0, %xmm1
	movapd	%xmm1, %xmm0
	movq	%xmm1, %rcx
	leaq	.LC5(%rip), %rax
	movapd	%xmm0, %xmm2
	movq	%rcx, %r8
	movq	%rax, %rcx
	call	__mingw_printf
	addl	$1, -4(%rbp)
.L27:
	movl	-4(%rbp), %eax
	cmpl	-16(%rbp), %eax
	jl	.L28
	movl	$0, %eax
	addq	$112, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.section .rdata,"dr"
	.align 8
.LC0:
	.long	0
	.long	1083129856
	.def	__main;	.scl	2;	.type	32;	.endef
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
	.def	imp;	.scl	2;	.type	32;	.endef
	.def	clock;	.scl	2;	.type	32;	.endef
	.def	atoi;	.scl	2;	.type	32;	.endef
