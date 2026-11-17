// 유명 관광지(관광공사 예측 대상). 좌표는 TourAPI searchKeyword2, tools/build_famous.py 로 생성
const FAMOUS = [
  {name:"성산일출봉", api:"성산일출봉 [유네스코 세계자연유산]", prof:"oreum", lat:33.4581, lng:126.9415},  // 성산일출봉 [유네스코 세계자연유산]
  {name:"우도", api:"우도(해양도립공원)", prof:"beach", lat:33.5195, lng:126.951},  // 우도
  {name:"협재해수욕장", api:"협재해수욕장", prof:"beach", lat:33.3937, lng:126.2394},  // 협재해수욕장
  {name:"비자림", api:"비자림", prof:"forest", lat:33.4862, lng:126.8075},  // 비자림
  {name:"월정리해변", api:"월정리해변(월정리해수욕장)", prof:"beach", lat:33.555, lng:126.7982},  // 월정리해변(월정리해수욕장)
  {name:"한담해변", api:"한담해변", prof:"coast", lat:33.4628, lng:126.3101},  // 한담해변
  {name:"새별오름", api:"새별오름", prof:"oreum", lat:33.3663, lng:126.3576},  // 새별오름
  {name:"쇠소깍", api:"쇠소깍", prof:"coast", lat:33.253, lng:126.6227},  // 쇠소깍
  {name:"섭지코지", api:"섭지코지", prof:"coast", lat:33.4236, lng:126.9297},  // 섭지코지
  {name:"함덕해수욕장", api:"함덕 서우봉 해변 (함덕해수욕장)", prof:"beach", lat:33.5439, lng:126.6683},  // 함덕해수욕장 (함덕 서우봉 해변)
  {name:"천지연폭포", api:"천지연폭포 (제주도 국가지질공원)", prof:"forest", lat:33.2447, lng:126.5596},  // 천지연폭포
  {name:"정방폭포", api:"정방폭포", prof:"coast", lat:33.2447, lng:126.5731},  // 정방폭포
  {name:"중문색달해변", api:"중문·색달 해변", prof:"beach", lat:33.2442, lng:126.4056},  // 중문색달해수욕장
  {name:"용두암", api:"용두암", prof:"coast", lat:33.5148, lng:126.5125},  // 용두암
  {name:"만장굴", api:"만장굴 (제주도 국가지질공원)", prof:"forest", lat:33.528, lng:126.7707},  // 만장굴 (제주도 국가지질공원)
  {name:"산방산", api:"산방산(제주)", prof:"oreum", lat:33.2338, lng:126.3118},  // 산방산랜드
  {name:"오설록 티뮤지엄", api:"오설록 티뮤지엄", prof:"village", lat:33.3061, lng:126.2894},  // 오설록 티뮤지엄
  {name:"카멜리아힐", api:"카멜리아힐", prof:"forest", lat:33.2899, lng:126.3683},  // 카멜리아힐
  {name:"곽지해수욕장", api:"곽지해수욕장 (곽지과물해변)", prof:"beach", lat:33.4485, lng:126.3031},  // 곽지해수욕장
  {name:"금능해수욕장", api:"금능해수욕장", prof:"beach", lat:33.3903, lng:126.236},  // 금능해수욕장
  {name:"용머리해안", api:"용머리해안", prof:"coast", lat:33.2317, lng:126.3151},  // 용머리해안
  {name:"김녕해수욕장", api:"김녕성세기해변 (김녕해수욕장)", prof:"beach", lat:33.5572, lng:126.7366},  // 김녕해수욕장
  {name:"표선해수욕장", api:"표선 해비치 해변", prof:"beach", lat:33.3256, lng:126.8424},  // 표선해수욕장
  {name:"천제연폭포", api:"천제연폭포", prof:"forest", lat:33.2526, lng:126.4184},  // 천제연폭포
  {name:"외돌개", api:"외돌개(제주)", prof:"coast", lat:33.2403, lng:126.5462},  // 외돌개(제주)
  {name:"송악산", api:"송악산", prof:"oreum", lat:33.1989, lng:126.2903},  // 송악산
  {name:"아부오름", api:"아부오름", prof:"oreum", lat:33.4473, lng:126.7776},  // 아부오름
  {name:"용눈이오름", api:"용눈이오름", prof:"oreum", lat:33.4588, lng:126.832},  // 용눈이오름
  {name:"금오름", api:"금오름", prof:"oreum", lat:33.3555, lng:126.3059},  // 금오름
  {name:"절물자연휴양림", api:"제주절물자연휴양림", prof:"forest", lat:33.44, lng:126.6252},  // 제주절물자연휴양림
  {name:"광치기해변", api:"광치기해변", prof:"coast", lat:33.4515, lng:126.9246},  // 광치기해변
  {name:"한라산", api:"한라산 (제주도 국가지질공원)", prof:"forest", lat:33.3618, lng:126.53},  // 한라산
  {name:"1100고지습지", api:"1100고지습지", prof:"forest", lat:33.3576, lng:126.463},  // 1100고지습지
  {name:"동문재래시장", api:"동문재래시장", prof:"village", lat:33.5115, lng:126.526},  // 동문재래시장
  {name:"서귀포매일올레시장", api:"서귀포매일올레시장", prof:"village", lat:33.2502, lng:126.5632},  // 서귀포매일올레시장
  {name:"보롬왓", api:"보롬왓", prof:"village", lat:33.4135, lng:126.7525},  // 보롬왓
];
