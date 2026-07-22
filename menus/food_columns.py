"""fetch_food_columns 명령이 생성한 미식 칼럼 목록. 직접 수정 금지."""
# COLUMNS = {"michelin": [{title,image,url}], "bluer": [...]}

COLUMNS = {
    'michelin': [
        {"title": '[레시피] 온지음이 전하는 가을의 맛, 궁중식 두부전골', "image": 'https://d3h1lg3ksw6i6b.cloudfront.net/media/image/2025/11/06/55b97c0ec1564c148aa1f0896017baaa_onjium-seoul-tofu-hotpot-pot_resized.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/how-to-make-court-inspired-tofu-hotpot-like-onjium'},
        {"title": '[레시피] 식사의 끝, 김치찌개의 시작 – 금돼지식당에서', "image": 'https://d3h1lg3ksw6i6b.cloudfront.net/media/image/2025/04/29/35ca9aad6eb742408e0459fe79c2d15e_.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/how-to-make-kimchi-jjigae-like-geumdwaeji-sikdang-a-beloved-seoul-institution-with-michelin-bib-gourmand-recognition-copy1'},
        {"title": '[레시피] 피오또: 그린스타의 철학으로 완성된 미각의 페어링', "image": 'https://d3h1lg3ksw6i6b.cloudfront.net/media/image/2025/04/29/2b20a81ab0474be6997a1eabcf421beb_fiotto_kombucha.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/how-to-make-kombucha-like-a-michelin-green-star-restaurant-kr'},
        {"title": '[레시피] 엘 초코 데 떼레노 신승환 셰프의 바스크 치즈 케이크', "image": 'https://img1.daumcdn.net/thumb/R1280x0/?scode=mtistory2&fname=https%3A%2F%2Fblog.kakaocdn.net%2Fdn%2FcbkLJw%2Fbtq9O65YcmK%2F2z3HzOOoncgma6won5rfPk%2Fimg.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/recipe-basque-burnt-cheesecake-el-txoko-de-terreno'},
        {"title": '피에르 에르메 셰프의 초콜릿 마카롱 레시피', "image": 'https://d3h1lg3ksw6i6b.cloudfront.net/media/image/2020/09/28/7eac6a0ff9464a3dbc2446b260fa7a9f_Profil-Hero-Image.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/recipe-pierre-herme-macaron-kr'},
        {"title": '[레시피] 안티트러스트 장진모 셰프의 감태 비빔국수', "image": 'https://img1.daumcdn.net/thumb/R1280x0/?scode=mtistory2&fname=https%3A%2F%2Fblog.kakaocdn.net%2Fdn%2FHKS10%2Fbtq0Oj7ofB8%2Fd55tJLMk9R3lahCHHckdt0%2Fimg.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/chef-jinmo-jang-antitrust-recipe'},
        {"title": '레시피: 묘미 김정묵 셰프의 젓갈 비빔면', "image": 'https://img1.daumcdn.net/thumb/R1280x0/?scode=mtistory2&fname=https%3A%2F%2Fk.kakaocdn.net%2Fdn%2FXgEUI%2FbtqDEFxKxBm%2FNPH1d2IChlKPnkF0pdo95k%2Fimg.jpg', "url": 'https://guide.michelin.com/kr/ko/article/dining-in/recipe-myomi-15-minute-recipe-kr'},
    ],
    'bluer': [
        {"title": '일본 오하요유업 ‘오하요 브륄레 밀크’,  세븐일레븐 통해 국내 정식 출시', "image": 'https://www.bluer.co.kr/images/es_58cf118810a54c8ab820fa3bfa63003e.jpg', "url": 'https://www.bluer.co.kr/magazine/657'},
        {"title": '7월의 뉴테이스트 by 김혜준 푸드 콘텐츠 디렉터', "image": 'https://www.bluer.co.kr/images/es_34fa1c71273a4413ab1aaa842b78be83.jpg', "url": 'https://www.bluer.co.kr/magazine/656'},
        {"title": '여름의 이국적인 해방감, 스페인 타파스 바', "image": 'https://www.bluer.co.kr/images/es_f162d6ba7b6246f99c6eefb3dc5a894e.jpg', "url": 'https://www.bluer.co.kr/magazine/655'},
        {"title": '2026 블루리본과 함께하는 중국 샤먼 미식 투어', "image": 'https://www.bluer.co.kr/images/es_9095473f142a4780bdd4a5418815947f.png', "url": 'https://www.bluer.co.kr/magazine/654'},
        {"title": '여름의 맛, 이색 면 맛집 7', "image": 'https://www.bluer.co.kr/images/es_9d7bfac97b4c4014b3ed99dee8cc67e6.jpg', "url": 'https://www.bluer.co.kr/magazine/653'},
        {"title": '서울에서 즐기는 블루리본 선정 간장게장 맛집', "image": 'https://www.bluer.co.kr/images/es_11b48043a89b47fab231a87fcb91e757.jpg', "url": 'https://www.bluer.co.kr/magazine/652'},
        {"title": '강원도의 재료를 담은 한식 다이닝, 예미헌', "image": 'https://www.bluer.co.kr/images/es_483bada6b4954c9a98d712f393d0d408.jpg', "url": 'https://www.bluer.co.kr/magazine/651'},
        {"title": '도심 속 피서지, 홍제천 미식 산책', "image": 'https://www.bluer.co.kr/images/es_6a53c42b3002476e8450d909df91d953.jpg', "url": 'https://www.bluer.co.kr/magazine/650'},
    ],
}
