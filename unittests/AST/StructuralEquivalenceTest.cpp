#include "clang/AST/ASTContext.h"
#include "clang/AST/ASTImporter.h"
#include "clang/ASTMatchers/ASTMatchers.h"
#include "clang/AST/ASTStructuralEquivalence.h"
#include "clang/Frontend/ASTUnit.h"
#include "clang/Tooling/Tooling.h"

#include "Language.h"
#include "DeclMatcher.h"

#include "gtest/gtest.h"

namespace clang {
namespace ast_matchers {

struct StructuralEquivalenceTest : ::testing::Test {
  std::unique_ptr<ASTUnit> AST0, AST1;
  std::string Code0, Code1; // Buffers for SourceManager

  // Get a pair of node pointers into the synthesized AST from the given code
  // snippets. To determine the returned node, a separate matcher is specified
  // for both snippets. The first matching node is returned.
  template <typename NodeType, typename MatcherType>
  std::tuple<NodeType *, NodeType *> makeDecls(
      const std::string &SrcCode0, const std::string &SrcCode1, Language Lang,
      const MatcherType &Matcher0, const MatcherType &Matcher1) {
    this->Code0 = SrcCode0;
    this->Code1 = SrcCode1;
    StringVector Args;
    getLangArgs(Lang, Args);

    const char *const InputFileName = "input.cc";

    AST0 = tooling::buildASTFromCodeWithArgs(Code0, Args, InputFileName);
    AST1 = tooling::buildASTFromCodeWithArgs(Code1, Args, InputFileName);

    NodeType *d0 = FirstDeclMatcher<NodeType>().match(
        AST0->getASTContext().getTranslationUnitDecl(), Matcher0);
    NodeType *d1 = FirstDeclMatcher<NodeType>().match(
        AST1->getASTContext().getTranslationUnitDecl(), Matcher1);

    return std::make_tuple(d0, d1);
  }
  
  // Get a pair of node pointers into the synthesized AST from the given code
  // snippets. The same matcher is used for both snippets.
  template <typename NodeType, typename MatcherType>
  std::tuple<NodeType *, NodeType *> makeDecls(
      const std::string &SrcCode0, const std::string &SrcCode1, Language Lang,
      const MatcherType &AMatcher) {
    return makeDecls<NodeType, MatcherType>(
          SrcCode0, SrcCode1, Lang, AMatcher, AMatcher);
  }

  // Get a pair of Decl pointers to the synthesized declarations from the given
  // code snippets. We search for the first NamedDecl with given name in both
  // snippets.
  std::tuple<NamedDecl *, NamedDecl *> makeNamedDecls(
      const std::string &SrcCode0, const std::string &SrcCode1,
      Language Lang, const char *const Identifier = "foo") {
    auto Matcher = namedDecl(hasName(Identifier));
    return makeDecls<NamedDecl>(SrcCode0, SrcCode1, Lang, Matcher);
  }
  
  bool testStructuralMatch(NamedDecl *d0, NamedDecl *d1) {
    llvm::DenseSet<std::pair<Decl *, Decl *>> NonEquivalentDecls;
    StructuralEquivalenceContext Ctx(d0->getASTContext(), d1->getASTContext(),
                                     NonEquivalentDecls, false, false);
    return Ctx.IsEquivalent(d0, d1);
  }
};

using std::get;

TEST_F(StructuralEquivalenceTest, Int) {
  auto t = makeNamedDecls("int foo;", "int foo;", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, IntVsSignedInt) {
  auto t = makeNamedDecls("int foo;", "signed int foo;", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, Char) {
  auto t = makeNamedDecls("char foo;", "char foo;", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, CharVsSignedChar) {
  auto t = makeNamedDecls("char foo;", "signed char foo;", Lang_CXX);
  // TODO this should be false!
  // FIXME in clang::StructuralEquivalenceContext::Finish
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, ForwardRecordDecl) {
  auto t = makeNamedDecls("struct foo;", "struct foo;", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, IntVsSignedIntInStruct) {
  auto t = makeNamedDecls("struct foo { int x; };",
                          "struct foo { signed int x; };", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, CharVsSignedCharInStruct) {
  auto t = makeNamedDecls("struct foo { char x; };",
                          "struct foo { signed char x; };", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, IntVsSignedIntTemplateSpec) {
  auto t = makeDecls<ClassTemplateSpecializationDecl>(
      R"(template <class T> struct foo; template<> struct foo<int>{};)",
      R"(template <class T> struct foo; template<> struct foo<signed int>{};)",
      Lang_CXX,
      classTemplateSpecializationDecl());
  auto Spec0 = get<0>(t);
  auto Spec1 = get<1>(t);
  EXPECT_TRUE(testStructuralMatch(Spec0, Spec1));
}

TEST_F(StructuralEquivalenceTest, CharVsSignedCharTemplateSpec) {
  auto t = makeDecls<ClassTemplateSpecializationDecl>(
      R"(template <class T> struct foo; template<> struct foo<char>{};)",
      R"(template <class T> struct foo; template<> struct foo<signed char>{};)",
      Lang_CXX,
      classTemplateSpecializationDecl());
  auto Spec0 = get<0>(t);
  auto Spec1 = get<1>(t);
  EXPECT_FALSE(testStructuralMatch(Spec0, Spec1));
}

TEST_F(StructuralEquivalenceTest, CharVsSignedCharTemplateSpecWithInheritance) {
  auto t = makeDecls<ClassTemplateSpecializationDecl>(
      R"(
struct true_type{};
template <class T> struct foo;
template<> struct foo<char> : true_type {};
      )",
      R"(
struct true_type{};
template <class T> struct foo;
template<> struct foo<signed char> : true_type {};
      )",
      Lang_CXX,
      classTemplateSpecializationDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}


TEST_F(StructuralEquivalenceTest, WrongOrderInNamespace) {
  auto Code0 =
      R"(
namespace NS {
template <class T> class Base {
    int a;
};
class Derived : Base<Derived> {
};
}
void foo(NS::Derived &);
      )";
  auto t = makeNamedDecls( Code0, Code0, Lang_CXX);

  ASSERT_TRUE(get<0>(t) != nullptr);
  ASSERT_TRUE(get<1>(t) != nullptr);

  NamespaceDecl *NS =
      LastDeclMatcher<NamespaceDecl>().match(get<1>(t), namespaceDecl());
  ClassTemplateDecl *TD = LastDeclMatcher<ClassTemplateDecl>().match(
      get<1>(t), classTemplateDecl(hasName("Base")));

  // Reorder the decls, move the TD to the last place in the DC.
  NS->removeDecl(TD);
  NS->addDeclInternal(TD);

  // TODO this should be FALSE!
  // FIXME in clang::StructuralEquivalenceContext
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, WrongOrderOfFieldsInClass) {
  auto Code0 = "class X { int a; int b; };";
  auto t = makeNamedDecls( Code0, Code0, Lang_CXX, "X");

  ASSERT_TRUE(get<0>(t) != nullptr);
  ASSERT_TRUE(get<1>(t) != nullptr);

  CXXRecordDecl *RD = FirstDeclMatcher<CXXRecordDecl>().match(
      get<1>(t), cxxRecordDecl(hasName("X")));
  FieldDecl *FD =
      FirstDeclMatcher<FieldDecl>().match(get<1>(t), fieldDecl(hasName("a")));

  // Reorder the FieldDecls
  RD->removeDecl(FD);
  RD->addDeclInternal(FD);

  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

struct StructuralEquivalenceFunctionTest : StructuralEquivalenceTest {
};

TEST_F(StructuralEquivalenceFunctionTest, ParamConstWithRef) {
  auto t = makeNamedDecls("void foo(int&);",
                          "void foo(const int&);", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ParamConstSimple) {
  auto t = makeNamedDecls("void foo(int);",
                          "void foo(const int);", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
  // consider this OK
}

TEST_F(StructuralEquivalenceFunctionTest, Throw) {
  auto t = makeNamedDecls("void foo();",
                          "void foo() throw();", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, Noexcept) {
  auto t = makeNamedDecls("void foo();",
                          "void foo() noexcept;", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ThrowVsNoexcept) {
  auto t = makeNamedDecls("void foo() throw();",
                          "void foo() noexcept;", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ThrowVsNoexceptFalse) {
  auto t = makeNamedDecls("void foo() throw();",
                          "void foo() noexcept(false);", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ThrowVsNoexceptTrue) {
  auto t = makeNamedDecls("void foo() throw();",
                          "void foo() noexcept(true);", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, DISABLED_NoexceptNonMatch) {
  // The expression is not checked yet.
  auto t = makeNamedDecls("void foo() noexcept(false);",
                          "void foo() noexcept(true);", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, NoexceptMatch) {
  auto t = makeNamedDecls("void foo() noexcept(false);",
                          "void foo() noexcept(false);", Lang_CXX11);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, NoexceptVsNoexceptFalse) {
  auto t = makeNamedDecls("void foo() noexcept;",
                          "void foo() noexcept(false);", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, NoexceptVsNoexceptTrue) {
  auto t = makeNamedDecls("void foo() noexcept;",
                          "void foo() noexcept(true);", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ReturnType) {
  auto t = makeNamedDecls("char foo();",
                          "int foo();", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ReturnConst) {
  auto t = makeNamedDecls("char foo();",
                          "const char foo();", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ReturnRef) {
  auto t = makeNamedDecls("char &foo();",
                          "char &&foo();", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ParamCount) {
  auto t = makeNamedDecls("void foo(int);",
                          "void foo(int, int);", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ParamType) {
  auto t = makeNamedDecls("void foo(int);",
                          "void foo(char);", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ParamName) {
  auto t = makeNamedDecls("void foo(int a);",
                          "void foo(int b);", Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, Variadic) {
  auto t = makeNamedDecls("void foo(int x...);",
                          "void foo(int x);", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceFunctionTest, ParamPtr) {
  auto t = makeNamedDecls("void foo(int *);",
                          "void foo(int);", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

struct StructuralEquivalenceCXXMethodTest : StructuralEquivalenceTest {
};

TEST_F(StructuralEquivalenceCXXMethodTest, Virtual) {
  auto t = makeDecls<CXXMethodDecl>(
      "struct X { void foo(); };",
      "struct X { virtual void foo(); };", Lang_CXX,
      cxxMethodDecl(hasName("foo")));
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Pure) {
  auto t = makeNamedDecls("struct X { virtual void foo(); };",
                          "struct X { virtual void foo() = 0; };", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, DISABLED_Final) {
  // The final-ness is not checked yet.
  auto t = makeNamedDecls("struct X { virtual void foo(); };",
                          "struct X { virtual void foo() final; };", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Const) {
  auto t = makeNamedDecls("struct X { void foo(); };",
                          "struct X { void foo() const; };", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Static) {
  auto t = makeNamedDecls("struct X { void foo(); };",
                          "struct X { static void foo(); };", Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Ref1) {
  auto t = makeNamedDecls("struct X { void foo(); };",
                          "struct X { void foo() &&; };", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Ref2) {
  auto t = makeNamedDecls("struct X { void foo() &; };",
                          "struct X { void foo() &&; };", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, AccessSpecifier) {
  auto t = makeDecls<CXXMethodDecl>(
      "struct X { public: void foo(); };",
      "struct X { private: void foo(); };", Lang_CXX,
      cxxMethodDecl(hasName("foo")));
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Delete) {
  auto t = makeNamedDecls("struct X { void foo(); };",
                          "struct X { void foo() = delete; };", Lang_CXX11);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Constructor) {
  auto t = makeDecls<FunctionDecl>(
      "void foo();", "struct foo { foo(); };", Lang_CXX,
      functionDecl(), cxxConstructorDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, ConstructorParam) {
  auto t = makeDecls<CXXConstructorDecl>("struct X { X(); };",
                                         "struct X { X(int); };", Lang_CXX,
                                         cxxConstructorDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, ConstructorExplicit) {
  auto t = makeDecls<CXXConstructorDecl>("struct X { X(int); };",
                                         "struct X { explicit X(int); };",
                                         Lang_CXX11,
                                         cxxConstructorDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, ConstructorDefault) {
  auto t = makeDecls<CXXConstructorDecl>("struct X { X(); };",
                                         "struct X { X() = default; };",
                                         Lang_CXX11,
                                         cxxConstructorDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Conversion) {
  auto t = makeDecls<CXXConversionDecl>("struct X { operator bool(); };",
                                        "struct X { operator char(); };",
                                         Lang_CXX11,
                                         cxxConversionDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, Operator) {
  auto t = makeDecls<FunctionDecl>(
      "struct X { int operator +(int); };",
      "struct X { int operator -(int); };", Lang_CXX,
      functionDecl(hasOverloadedOperatorName("+")),
      functionDecl(hasOverloadedOperatorName("-")));
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, OutOfClass1) {
  auto t = makeDecls<FunctionDecl>(
      "struct X { virtual void f(); }; void X::f() { }",
      "struct X { virtual void f() { }; };",
      Lang_CXX,
      functionDecl(allOf(hasName("f"), isDefinition())));
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceCXXMethodTest, OutOfClass2) {
  auto t = makeDecls<FunctionDecl>(
      "struct X { virtual void f(); }; void X::f() { }",
      "struct X { void f(); }; void X::f() { }",
      Lang_CXX,
      functionDecl(allOf(hasName("f"), isDefinition())));
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

struct StructuralEquivalenceRecordTest : StructuralEquivalenceTest {
};

TEST_F(StructuralEquivalenceRecordTest, Name) {
  auto t = makeDecls<CXXRecordDecl>(
      "struct A{ };",
      "struct B{ };",
      Lang_CXX,
      cxxRecordDecl());
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, Fields) {
  auto t = makeNamedDecls(
      "struct foo{ int x; };",
      "struct foo{ char x; };",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, DISABLED_Methods) {
  auto t = makeNamedDecls(
      "struct foo{ int x(); };",
      "struct foo{ char x(); };",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, Bases) {
  auto t = makeNamedDecls(
      "struct A{ }; struct foo: A { };",
      "struct B{ }; struct foo: B { };",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, InheritanceVirtual) {
  auto t = makeNamedDecls(
      "struct A{ }; struct foo: A { };",
      "struct A{ }; struct foo: virtual A { };",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, DISABLED_InheritanceType) {
  // Access specifier in inheritance is not checked yet.
  auto t = makeNamedDecls(
      "struct A{ }; struct foo: public A { };",
      "struct A{ }; struct foo: private A { };",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceRecordTest, Match) {
  auto Code = R"(
      struct A{ };
      struct B{ };
      struct foo: A, virtual B {
        void x();
        int a;
      };
      )";
  auto t = makeNamedDecls(Code, Code, Lang_CXX);
  EXPECT_TRUE(testStructuralMatch(get<0>(t), get<1>(t)));
}

TEST_F(StructuralEquivalenceTest, CompareSameDeclWithMultiple) {
  auto t = makeNamedDecls(
      "struct A{ }; struct B{ }; void foo(A a, A b);",
      "struct A{ }; struct B{ }; void foo(A a, B b);",
      Lang_CXX);
  EXPECT_FALSE(testStructuralMatch(get<0>(t), get<1>(t)));
}

} // end namespace ast_matchers
} // end namespace clang
