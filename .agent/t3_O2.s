	.file	"t3.c"
	.text
	.p2align 4
	.globl	abc
	.def	abc;	.scl	2;	.type	32;	.endef
	.seh_proc	abc
abc:
	pushq	%rbx
	.seh_pushreg	%rbx
	.seh_endprologue
	testl	%ecx, %ecx
	movl	%edx, %eax
	jle	.L1
	leal	-1(%rcx), %r8d
	leal	-5(%rcx), %ebx
	leal	-4(%rcx), %r11d
	leal	-3(%rcx), %r10d
	leal	-2(%rcx), %r9d
.L3:
	leal	(%rdx,%rcx), %eax
	testl	%r8d, %r8d
	je	.L1
	addl	%r8d, %eax
	testl	%r9d, %r9d
	je	.L1
	addl	%r9d, %eax
	testl	%r10d, %r10d
	je	.L1
	addl	%r10d, %eax
	testl	%r11d, %r11d
	je	.L1
	addl	%r11d, %eax
	testl	%ebx, %ebx
	je	.L1
	leal	(%rax,%rbx), %edx
	subl	$6, %r8d
	subl	$6, %ebx
	subl	$6, %r11d
	subl	$6, %r10d
	subl	$6, %r9d
	subl	$6, %ecx
	jne	.L3
	movl	%edx, %eax
.L1:
	popq	%rbx
	ret
	.seh_endproc
	.p2align 4
	.globl	def
	.def	def;	.scl	2;	.type	32;	.endef
	.seh_proc	def
def:
	.seh_endprologue
	testl	%ecx, %ecx
	jle	.L24
	leal	(%rcx,%rdx), %eax
	movl	%ecx, %edx
	subl	$1, %edx
	je	.L22
	addl	%edx, %eax
	movl	%ecx, %edx
	subl	$2, %edx
	je	.L22
	addl	%edx, %eax
	movl	%ecx, %edx
	subl	$3, %edx
	je	.L22
	addl	%edx, %eax
	movl	%ecx, %edx
	subl	$4, %edx
	je	.L22
	addl	%edx, %eax
	movl	%ecx, %edx
	subl	$5, %edx
	je	.L22
	addl	%edx, %eax
	movl	%ecx, %edx
	subl	$6, %edx
	je	.L22
	addl	%eax, %edx
	subl	$7, %ecx
	jmp	abc
	.p2align 4,,10
	.p2align 3
.L24:
	movl	%edx, %eax
.L22:
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
